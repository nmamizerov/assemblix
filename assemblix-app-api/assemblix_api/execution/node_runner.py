"""Per-node execution mechanics, factored out of WorkflowExecutor.

The executor decides *which* node runs next (sequential pointer or parallel scheduler);
NodeRunner owns *how* a single node runs and is recorded — the identical bookkeeping both
traversal strategies need:

- run the node under the in-progress gauge,
- apply its state / project / history / cost outputs to the context,
- emit the debug `step_start` / `step_complete` events,
- write the ExecutionStep row (COMPLETED or FAILED) idempotently,
- push step / LLM metrics and checkpoint the DB connection.

Keeping this in one place removes the copy that the sequential and parallel loops used to
carry, and lets each loop read as pure traversal.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal

import structlog

from assemblix_api.billing.plans import credit_config
from assemblix_api.core.metrics import observe_step, set_nodes_in_progress, track_llm
from assemblix_api.core.settings import get_settings
from assemblix_api.enums import StepStatus
from assemblix_api.execution.cost_accumulator import accumulate_step_cost
from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.execution import (
    ExecutionContext,
    ExecutionStepData,
    NodeInput,
    NodeOutput,
)
from assemblix_api.services.execution_trace_service import ExecutionTracerService

logger = structlog.get_logger(__name__)


class NodeRunner:
    """Runs one node and records its step. Stateless across calls; safe to share."""

    def __init__(
        self,
        tracer: ExecutionTracerService,
        debug_event_manager: DebugEventManager,
        db_checkpoint: Callable[[], Awaitable[None]],
    ):
        self._tracer = tracer
        self._debug_event_manager = debug_event_manager
        # Commits the execution session at node boundaries so the DB connection is
        # released during long external awaits. No-op outside the queue/isolated path.
        self._db_checkpoint = db_checkpoint

    async def run(self, node, node_input: NodeInput) -> NodeOutput:
        """Execute the node under the in-progress gauge. Errors propagate."""
        set_nodes_in_progress(+1)
        try:
            return await node.execute(node_input)
        finally:
            set_nodes_in_progress(-1)

    async def emit_start(
        self,
        context: ExecutionContext,
        *,
        node_id: str,
        node_type: str,
        node_data: dict,
        state_before: dict,
        project_state_before: dict,
        step_number: int,
    ) -> None:
        """Log the node-start and emit the debug `step_start` event (if streaming)."""
        logger.info(
            "workflow.node.started",
            node_id=node_id,
            node_type=node_type,
            step_number=step_number,
        )
        if self._debug_event_manager.get_stream(context.execution_id):
            await self._debug_event_manager.emit_step_start(
                execution_id=context.execution_id,
                step_number=step_number,
                node_id=node_id,
                node_type=node_type,
                input_data=node_data,
                state_before=state_before,
                project_state_before=project_state_before,
            )

    async def record_failed(
        self,
        context: ExecutionContext,
        *,
        node_id: str,
        node_type: str,
        node_data: dict,
        state_before: dict,
        step_number: int,
        started_at: datetime,
        error: Exception,
    ) -> None:
        """Persist a FAILED ExecutionStep (idempotent) and emit the failure metric.

        The caller re-raises as NodeExecutionError; logging here means the upper handler
        doesn't reconstruct timing/payload and the UI shows the failed node alongside the
        successful ones. The idempotency guard avoids a duplicate row (violating the
        (execution_id, step_number) UniqueConstraint) on a resumed/redelivered run.
        """
        step_end = datetime.now()
        try:
            if not await self._tracer.has_step(
                execution_id=context.execution_id, step_number=step_number
            ):
                await self._tracer.log_step(
                    ExecutionStepData(
                        execution_id=context.execution_id,
                        step_number=step_number,
                        node_id=node_id,
                        node_type=node_type,
                        input_data=node_data,
                        output_data=None,
                        state_before=state_before,
                        state_after=None,
                        status=StepStatus.FAILED.value,
                        started_at=started_at,
                        completed_at=step_end,
                        duration_ms=int((step_end - started_at).total_seconds() * 1000),
                        error_message=str(error),
                        cel_evaluations=None,
                    )
                )
        except Exception as log_err:
            # Never let logging failure mask the original node error.
            logger.warning("workflow.step.log_failed", node_id=node_id, error=str(log_err))

        observe_step(node_type, "failed")

    async def record_completed(
        self,
        context: ExecutionContext,
        *,
        node_id: str,
        node_type: str,
        node_data: dict,
        node_output: NodeOutput,
        state_before: dict,
        step_number: int,
        started_at: datetime,
    ) -> ExecutionContext:
        """Apply a completed node's outputs, emit events, log the step, checkpoint.

        Returns the updated context (state / project_state / chat_history / cost folded
        in). Step numbering (with_node_visited) stays with the caller so the sequential
        and parallel loops keep their own numbering schemes.
        """
        step_end = datetime.now()
        duration_ms = int((step_end - started_at).total_seconds() * 1000)
        logger.info(
            "workflow.node.completed",
            node_id=node_id,
            node_type=node_type,
            step_number=step_number,
            duration_ms=duration_ms,
        )

        # Fold this node's outputs into the shared context (last-write per key).
        if node_output.state_updates:
            context = context.with_state(node_output.state_updates)
        if node_output.project_updates:
            context = context.with_project_state(node_output.project_updates)
        if node_output.history_append:
            context = context.with_chat_history([node_output.history_append])
        # Step cost is accumulated centrally (the node does not mutate billing).
        context = accumulate_step_cost(context, node_output.metadata)

        meta = node_output.metadata
        if self._debug_event_manager.get_stream(context.execution_id):
            # Credits are charged only when system keys are used.
            step_credits = None
            if meta and get_settings().billing_enabled:
                step_cost = meta.get("cost", 0)
                if step_cost and meta.get("used_system_key", False):
                    step_credits = float(
                        credit_config.usd_to_credits(Decimal(str(step_cost)), with_margin=True)
                    )
            await self._debug_event_manager.emit_step_complete(
                execution_id=context.execution_id,
                step_number=step_number,
                node_id=node_id,
                node_type=node_type,
                output_data=node_output.data,
                state_after=context.state,
                project_state_after=context.project_state,
                duration_ms=duration_ms,
                model_used=meta.get("model") if meta else None,
                tokens_used=meta.get("tokens") if meta else None,
                cost=meta.get("cost") if meta else None,
                own_key_cost_usd=meta.get("own_key_cost_usd") if meta else None,
                credits_used=step_credits,
                llm_request=meta.get("llm_request") if meta else None,
            )

        # Log the COMPLETED ExecutionStep (idempotency guard against a resumed run that
        # already wrote this step_number).
        # Audio rides the live response / SSE only — keep it out of the persisted step.
        persisted_step_output = node_output.data
        if isinstance(node_output.data, dict) and "audio" in node_output.data:
            persisted_step_output = {k: v for k, v in node_output.data.items() if k != "audio"}

        if not await self._tracer.has_step(
            execution_id=context.execution_id, step_number=step_number
        ):
            await self._tracer.log_step(
                ExecutionStepData(
                    execution_id=context.execution_id,
                    step_number=step_number,
                    node_id=node_id,
                    node_type=node_type,
                    input_data=node_data,
                    output_data=persisted_step_output,
                    state_before=state_before,
                    state_after=context.state,
                    status=StepStatus.COMPLETED.value,
                    started_at=started_at,
                    completed_at=step_end,
                    duration_ms=duration_ms,
                    error_message=None,
                    model_used=meta.get("model") if meta else None,
                    own_key_cost_usd=meta.get("own_key_cost_usd") if meta else None,
                    cel_evaluations=None,
                    llm_request=meta.get("llm_request") if meta else None,
                )
            )

        observe_step(node_type, "completed")
        track_llm(
            model=meta.get("model") if meta else None,
            tokens=meta.get("tokens") if meta else None,
            cost_usd=meta.get("cost") if meta else None,
        )
        # Commit this step and release the DB connection between nodes.
        await self._db_checkpoint()
        return context
