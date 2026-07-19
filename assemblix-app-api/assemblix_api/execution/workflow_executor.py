# /execution/workflow_executor.py

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from assemblix_api.core.cel_evaluator import CELEvaluator
from assemblix_api.core.node_registry import NodeRegistry
from assemblix_api.core.settings import get_settings
from assemblix_api.core.template_evaluator import TemplateEvaluator
from assemblix_api.database.models.execution import Execution
from assemblix_api.database.models.workflow import Workflow
from assemblix_api.execution.credential_resolver import CredentialResolver
from assemblix_api.services import (
    ChatMessageService,
    ChatService,
    ExecutionService,
)
from assemblix_api.services.client_session_service import ClientSessionService
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.execution_trace_service import ExecutionTracerService
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService
from assemblix_api.services.organization_service import OrganizationService
from assemblix_api.services.project_service import ProjectService

if TYPE_CHECKING:
    from assemblix_api.billing.credit_service import CreditService
    from assemblix_api.execution.resume import ResumePoint
from assemblix_api.core.metrics import observe_execution
from assemblix_api.enums import NodeType
from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.execution.graph_navigator import GraphNavigator
from assemblix_api.execution.node_runner import NodeRunner
from assemblix_api.schemas.execution import (
    AudioInput,
    ExecutionContext,
    ExecutionResult,
    ExecutionResultMetadata,
    ExecutionStepData,
    NodeInput,
    NodeOutput,
    _noop_checkpoint,
)
from assemblix_api.schemas.node import BaseNode, StartNodeConfig
from assemblix_api.utils import coerce_to_type, get_typed_default_value

logger = structlog.get_logger(__name__)


def _passthrough_branch_scope(
    base_ctx: ExecutionContext,
) -> AbstractAsyncContextManager[ExecutionContext]:
    """Default branch scope: yield the base context unchanged (sequential path / tests)."""

    @asynccontextmanager
    async def _cm() -> AsyncIterator[ExecutionContext]:
        yield base_ctx

    return _cm()


class WorkflowExecutor:
    """
    Main orchestrator for workflow execution.
    Handles preparation, execution loop, finalization.
    """

    # Class-level default so instances built via __new__ (some unit tests bypass
    # __init__) still have a safe no-op checkpoint; __init__ overrides per-instance.
    _db_checkpoint: Callable[[], Awaitable[None]] = staticmethod(_noop_checkpoint)

    def __init__(
        self,
        execution_service: ExecutionService,
        chat_service: ChatService,
        tracer: ExecutionTracerService,
        node_registry: NodeRegistry,
        cel_evaluator: CELEvaluator,
        credential_service: CredentialsService,
        chat_message_service: ChatMessageService,
        debug_event_manager: DebugEventManager,
        client_session_service: ClientSessionService,
        project_service: ProjectService,
        organization_service: OrganizationService,
        credit_service: "CreditService",
        knowledge_base_service: KnowledgeBaseService | None = None,
        db_checkpoint: Callable[[], Awaitable[None]] | None = None,
        branch_scope: Callable[[ExecutionContext], AbstractAsyncContextManager[ExecutionContext]]
        | None = None,
    ):
        self._execution_service = execution_service
        self._chat_service = chat_service
        self._tracer = tracer
        self._node_registry = node_registry
        self._cel_evaluator = cel_evaluator
        self._credential_service = credential_service
        self._chat_message_service = chat_message_service
        self._debug_event_manager = debug_event_manager
        self._client_session_service = client_session_service
        self._project_service = project_service
        self._organization_service = organization_service
        self._credit_service = credit_service
        self._knowledge_base_service = knowledge_base_service
        # Commits the execution session at node boundaries so the DB connection is
        # released during long external awaits. No-op when not wired (request scope/tests).
        self._db_checkpoint = db_checkpoint if db_checkpoint is not None else _noop_checkpoint
        self._navigator = GraphNavigator()
        # Owns per-node execution mechanics (run + step recording) shared by both loops.
        self._node_runner = NodeRunner(self._tracer, self._debug_event_manager, self._db_checkpoint)
        # Per-branch session scope for the parallel engine; passthrough when not wired
        # (sequential path and unit tests share the run session, which is fine there).
        self._branch_scope = branch_scope if branch_scope is not None else _passthrough_branch_scope

    async def execute(
        self,
        workflow: Workflow,
        input_data: dict,
        token_id: UUID | None = None,
        chat_session_id: UUID | None = None,
        on_execution_created: Callable[[UUID], Awaitable[None]] | None = None,
        execution_id: UUID | None = None,
        audio_input: AudioInput | None = None,
    ) -> ExecutionResult:
        """
        Main execution entry point.

        Flow:
        1. Preparation (create execution, load state, create context)
        2. Execution loop (traverse graph, execute nodes, log steps)
        3. Finalization (save state, update execution)

        Args:
            workflow: Workflow to execute
            input_data: Input data for workflow
            token_id: ID of API key (token) executing the workflow (None for debug mode)
            chat_session_id: Optional chat session for stateful execution
            on_execution_created: Callback fired after the execution record is created
            execution_id: When provided, reuse an existing pre-created (QUEUED) execution
                          instead of creating a new one. The row is loaded and transitioned
                          to RUNNING. When None (default), a new execution row is created
                          — this path is byte-for-byte unchanged.
            audio_input: Raw audio for this turn (voice endpoints), attached to the
                         execution context for nodes that consume it directly.

        Returns:
            ExecutionResult with output and metadata
        """
        execution = None
        context = None

        try:
            # 1. Preparation phase
            execution, context, resume_point = await self._preparation_phase(
                workflow,
                input_data,
                token_id,
                chat_session_id,
                execution_id=execution_id,
                audio_input=audio_input,
            )

            # Bind execution context for all subsequent logs inside this task.
            structlog.contextvars.bind_contextvars(
                execution_id=str(execution.id),
                workflow_id=str(workflow.id),
                project_id=str(workflow.project_id),
            )
            logger.info(
                "workflow.execution.started",
                token_id=str(token_id) if token_id else None,
                chat_session_id=str(chat_session_id) if chat_session_id else None,
            )

            # 1.5. Notify caller that execution record has been created
            if on_execution_created is not None:
                await on_execution_created(execution.id)

            # 2. Execution loop
            (
                final_output,
                context,
                is_session_end,
                is_error,
                error_message,
            ) = await self._execution_loop(context, resume_point=resume_point)

            # 3. Finalization phase
            await self._finalization_phase(
                execution,
                context,
                final_output,
                is_session_end,
                is_error,
                error_message,
            )

            # 4. Determine status
            status = "error" if is_error else "completed"

            # Emit execution-level metric now that duration_ms has been written
            # by _finalization_phase → update_execution_status.
            observe_execution(status, (execution.duration_ms or 0) / 1000)

            logger.info(
                "workflow.execution.completed",
                status=status,
                nodes_executed=context.step_number,
                duration_ms=execution.duration_ms,
                total_credits=float(execution.total_credits),
                error_message=error_message if is_error else None,
            )

            # 5. Return result
            return ExecutionResult(
                execution_id=execution.id,
                status=status,
                output=final_output,
                final_state=context.state,
                final_project_state=context.project_state,
                metadata=ExecutionResultMetadata(
                    total_credits=float(execution.total_credits),
                    steps_count=context.step_number,
                    duration_ms=execution.duration_ms,
                    own_key_cost_usd=(
                        float(execution.own_key_cost_usd)
                        if execution.own_key_cost_usd is not None
                        else None
                    ),
                    error_message=error_message if is_error else None,
                ),
                session_id=context.chat_session_id,
                is_session_closed=is_session_end,
            )

        except Exception as error:
            # Handle error if we have execution context
            if execution and context:
                from assemblix_api.execution.error_taxonomy import classify_error
                from assemblix_api.execution.exceptions import NodeExecutionError

                # Extract node_id and original error from NodeExecutionError
                if isinstance(error, NodeExecutionError):
                    failed_node_id = error.node_id
                    original_error = error.original_error
                else:
                    failed_node_id = None
                    original_error = error

                # Classify transient vs fatal — foundation for retries (Phase 3).
                transience = classify_error(original_error)

                logger.exception(
                    "workflow.execution.failed",
                    failed_node_id=failed_node_id,
                    error_type=type(original_error).__name__,
                    transience=transience.value,
                )

                # Return ExecutionResult with error info instead of raising
                return await self._handle_error(
                    execution, context, original_error, failed_node_id=failed_node_id
                )
            raise

    async def _preparation_phase(
        self,
        workflow: Workflow,
        input_data: dict,
        token_id: UUID | None,
        chat_session_id: UUID | None,
        execution_id: UUID | None = None,
        audio_input: AudioInput | None = None,
    ) -> tuple[Execution, ExecutionContext, "ResumePoint | None"]:
        """
        Create (or load) execution record and build execution context.

        When execution_id is None (default): creates a new Execution row with
        status=RUNNING — the original behavior, unchanged.

        When execution_id is provided: loads the existing row (expected status
        QUEUED) and transitions it to RUNNING via mark_running(). All subsequent
        preparation steps (state loading, context construction) are identical for
        both paths.

        Resume logic (Task E2):
        When execution_checkpointing_enabled is True AND execution_id is not None,
        all existing steps are fetched and find_resume_point() is called. If it
        returns a non-None ResumePoint, the context is seeded with the recovered
        state and step_number. project_state is intentionally kept from
        initial_project_state (loaded from ClientSession), not from the empty
        ResumePoint.project_state — ExecutionStep has no project_state column.
        The ResumePoint is returned as the third element so _execution_loop can
        start the graph traversal from the node after last_node_id.

        Returns:
            (execution, context, resume_point) — resume_point is None when not resuming.

        Steps:
        1. Check if debug mode
        2. Handle client_id (create/get ClientSession)
        3. Check create_session flag and create session if needed
        4. Save user message (if stateful)
        5. Load initial state and project state
        6. Create or load execution record
        7. Create workflow definition
        8. Create execution context (seeded from resume point if applicable)
        9. Create debug stream if debug mode
        """
        from assemblix_api.schemas.workflow import WorkflowDefinition

        # 1. Check if debug mode / streaming
        is_debug = input_data.get("is_debug", False)
        stream_enabled = input_data.get("stream", False)

        # 2. Handle client_id (create/get ClientSession if needed)
        client_id = input_data.get("client_id")
        client_metadata = input_data.get("metadata", {})
        client_session_id = None

        if client_id:
            # Load project to get state_schema
            project = await self._project_service.get_by_id(workflow.project_id)

            # Calculate initial project state from schema
            initial_project_state = {}
            for var in project.state_schema:
                initial_project_state[var["name"]] = get_typed_default_value(var)

            # Get or create ClientSession
            client_session = await self._client_session_service.get_or_create_by_client_id(
                project_id=workflow.project_id,
                client_id=client_id,
                initial_state=initial_project_state,
                is_debug=is_debug,
            )
            client_session_id = client_session.id

            # Update metadata if provided
            if client_metadata:
                await self._client_session_service.update_metadata(
                    session_id=client_session_id,
                    metadata_updates=client_metadata,
                )

            # Sync schema (add new variables if project.state_schema was updated)
            await self._client_session_service.sync_schema(
                session_id=client_session_id,
                project_state_schema=project.state_schema,
            )

        # 3. Check create_session flag
        create_session_flag = input_data.get("create_session", False)
        is_new_session = False
        first_phrase: str | None = None

        if create_session_flag and chat_session_id is None:
            # Calculate default state from workflow definition
            workflow_def_temp = WorkflowDefinition.from_workflow(workflow)
            default_state = {}
            for var in workflow_def_temp.state_schema:
                default_state[var.name] = var.default_value

            # Extract session_name from input_data
            session_name = input_data.get("session_name")

            # Create new chat session with default state
            session = await self._chat_service.create_session(
                workflow_id=workflow.id,
                token_id=token_id,  # API key used for this execution
                initial_state=default_state,
                is_debug=is_debug,
                name=session_name,
            )
            chat_session_id = session.id
            is_new_session = True

            # First phrase: the assistant greeting is persisted as a real message in the
            # new session (before the user message) so the DB order is greeting -> user ->
            # answer. On later turns it is pulled from history instead.
            from assemblix_api.enums import MessageRole

            start_node_id = self._navigator.find_start_node(workflow.nodes)
            start_node = next((n for n in workflow.nodes if n["id"] == start_node_id), None)
            start_cfg = StartNodeConfig(**((start_node or {}).get("config") or {}))
            if start_cfg.first_phrase:
                first_phrase = start_cfg.first_phrase
                await self._chat_message_service.save_message(
                    chat_session_id=chat_session_id,
                    role=MessageRole.ASSISTANT,
                    content=first_phrase,
                )

        # 4. Build in-memory chat_history (single source of truth during execution).
        # Persistent history is loaded once here; nodes do not hit the DB.
        # User message is persisted in finalization phase (only on success path).
        chat_history: list[dict] = []
        if chat_session_id and not is_new_session:
            chat_history = await self._chat_message_service.get_chat_history(
                chat_session_id=chat_session_id,
                limit=20,
            )

        # New session with a greeting: the phrase is already in the DB, but for the
        # current run it must be first in the in-memory history, before the user message.
        if is_new_session and first_phrase:
            chat_history.append({"role": "assistant", "content": first_phrase})

        user_message = input_data.get("message", "")
        if user_message:
            chat_history.append({"role": "user", "content": user_message})

        # 5. Load initial state and project state
        custom_state = input_data.get("state")
        custom_project_state = input_data.get("project_state")
        initial_state, initial_project_state = await self._load_initial_state(
            workflow,
            chat_session_id,
            client_session_id,
            custom_state,
            custom_project_state,
        )

        # 6. Create or load execution record.
        # When execution_id is provided we reuse the pre-created row (QUEUED → RUNNING).
        # Otherwise the original create path runs unchanged.
        if execution_id is not None:
            # mark_running loads the row and flips its status to RUNNING.
            execution = await self._execution_service.mark_running(execution_id)
        else:
            execution = await self._execution_service.create_execution(
                workflow_id=workflow.id,
                token_id=token_id,  # API key used for this execution
                chat_session_id=chat_session_id,
                client_session_id=client_session_id,  # NEW: Client session ID
                initial_state=initial_state,
                input_data=input_data,
                is_debug=is_debug,
            )

        # 7. Create workflow definition
        workflow_def = WorkflowDefinition.from_workflow(workflow)

        # 8. Get organization info for billing
        project = await self._project_service.get_by_id(workflow.project_id)
        organization = await self._organization_service.get_by_id(project.organization_id)

        # 9. Optionally compute resume point when checkpointing is enabled and we have
        # a pre-created execution.  Default to None (fresh start) for both paths.
        from assemblix_api.execution.resume import ResumePoint, find_resume_point

        resume_point: ResumePoint | None = None
        if get_settings().execution_checkpointing_enabled and execution_id is not None:
            steps = await self._tracer.get_steps(execution.id)
            resume_point = find_resume_point(steps)

        # Determine context seed values: either from resume point or initial state.
        if resume_point is not None:
            context_state = resume_point.state.copy()
            context_step_number = resume_point.next_step_number
            # project_state is NOT checkpointed per step; reload from ClientSession
            # (initial_project_state) rather than the empty ResumePoint.project_state.
            context_project_state = initial_project_state.copy()
        else:
            context_state = initial_state.copy()
            context_step_number = 0
            context_project_state = initial_project_state.copy()

        # 10. Create execution context
        context = ExecutionContext(
            execution_id=execution.id,
            workflow_id=workflow.id,
            project_id=workflow.project_id,  # Project ID for credentials access
            user_id=token_id,  # API key used for this execution (optional for debug mode)
            workflow=workflow_def,
            state=context_state,
            project_state=context_project_state,
            chat_session_id=chat_session_id,
            client_session_id=client_session_id,  # NEW: Client session ID
            input_data=input_data,
            step_number=context_step_number,
            visited_nodes=[],
            node_execution_count={},
            cel_evaluator=self._cel_evaluator,
            template_evaluator=TemplateEvaluator(self._cel_evaluator),
            credential_resolver=CredentialResolver(self._credential_service),
            credential_service=self._credential_service,
            chat_message_service=self._chat_message_service,
            execution_tracer_service=self._tracer,
            knowledge_base_service=self._knowledge_base_service,
            # Billing
            organization_id=organization.id,
            organization_plan=organization.plan,
            chat_history=chat_history,
            db_checkpoint=self._db_checkpoint,
            stream_enabled=stream_enabled,
            audio_input=audio_input,
        )

        # 11. Open the event stream. Debug uses the legacy queue+buffer (create_stream);
        # a streaming-only run opens the buffer alone (no undrained queue).
        if is_debug:
            self._debug_event_manager.create_stream(execution.id)
            # Only the legacy single-request debug SSE waits for the client; a streaming run
            # (task=true) runs freely and the buffer lets a late subscriber catch up.
            await self._debug_event_manager.wait_for_client(execution.id, timeout=10.0)
        elif stream_enabled:
            self._debug_event_manager.open_buffer(execution.id)

        return execution, context, resume_point

    async def _execution_loop(
        self,
        context: ExecutionContext,
        resume_point: "ResumePoint | None" = None,
    ) -> tuple[dict, ExecutionContext, bool, bool, str]:
        """Traverse and execute the node graph.

        Dispatches between two engines:
        - The **parallel** scheduler (fork/join, dead-path elimination) for graphs that
          actually branch — a real AND-split (a non-CONDITION node with 2+ outgoing
          edges) or a join (a node with 2+ incoming edges).
        - The **sequential** single-pointer loop for everything else (linear / condition
          / bounded-loop graphs) and for all resume paths. This is the original,
          battle-tested engine, byte-for-byte unchanged, so non-parallel workflows keep
          their exact behavior.
        """
        if resume_point is not None:
            # Crash-resume is linear-only in v1 (see resume.py); always sequential.
            return await self._execution_loop_sequential(context, resume_point)
        if self._has_parallelism(context.workflow.nodes, context.workflow.edges):
            return await self._execution_loop_parallel(context)
        return await self._execution_loop_sequential(context, None)

    @staticmethod
    def _has_parallelism(nodes: list[dict], edges) -> bool:
        """Whether the graph needs the parallel engine: a genuine fork or a join.

        A CONDITION with several outgoing edges is a router (one branch taken), not a
        fork, so it does not count. Edges to missing nodes and self-loops are ignored,
        matching the traversal rules.
        """
        from collections import defaultdict

        node_ids = {n["id"] for n in nodes}
        node_type = {n["id"]: n.get("type") for n in nodes}
        out_targets: dict[str, set[str]] = defaultdict(set)
        in_sources: dict[str, set[str]] = defaultdict(set)
        for e in edges:
            if e.target not in node_ids or e.source not in node_ids or e.target == e.source:
                continue
            out_targets[e.source].add(e.target)
            in_sources[e.target].add(e.source)

        for source, targets in out_targets.items():
            if len(targets) >= 2 and node_type.get(source) != NodeType.CONDITION.value:
                return True  # AND-split (parallel fork)
        return any(len(srcs) >= 2 for srcs in in_sources.values())  # join

    async def _execution_loop_sequential(
        self,
        context: ExecutionContext,
        resume_point: "ResumePoint | None" = None,
    ) -> tuple[dict, ExecutionContext, bool, bool, str]:
        """
        Main loop - traverse and execute nodes.

        Process:
        1. Find START node (or resume after last completed node)
        2. Loop:
           - Check cycle detection
           - Execute node
           - Log step
           - Update context
           - Find next node
           - Break if END node

        Args:
            context:      Execution context (state already seeded from resume point
                          by _preparation_phase when applicable).
            resume_point: When not None, the loop starts at the node AFTER
                          resume_point.last_node_id instead of the START node.
                          previous_output is seeded from the last completed step's
                          output_data.  When None, the normal fresh-start path runs
                          unchanged.

        Returns:
            Tuple of (final_output, context, is_session_end, is_error, error_message)
        """
        from assemblix_api.execution.exceptions import (
            MaxStepsExceededError,
            NodeExecutionLimitError,
            NoNextNodeError,
            WorkflowTimeoutError,
        )

        # Global wall-clock deadline — guard against runaway workflows.
        execution_deadline = time.monotonic() + get_settings().workflow_execution_timeout_seconds

        # 1. Determine starting node and initial previous_output.
        if resume_point is not None:
            # Resume path: jump to the node after the last completed one.
            current_node_id = self._navigator.find_next_node(
                context.workflow.edges,
                context.workflow.nodes,
                resume_point.last_node_id,
                resume_point.condition_index,
            )
            if current_node_id is None:
                # The last completed node had no successor (e.g. was an END node).
                # Treat as already finished — return empty output gracefully.
                return {}, context, False, False, ""
            previous_output = resume_point.last_output
        else:
            # Fresh start: begin at the START node with no previous output.
            current_node_id = self._navigator.find_start_node(context.workflow.nodes)
            previous_output = None

        # Track session end flag
        is_session_end = False

        # 2. Main loop
        while True:
            # Global wall-clock budget check (before each node)
            if time.monotonic() > execution_deadline:
                raise WorkflowTimeoutError(
                    "Workflow execution exceeded the global time budget "
                    f"({get_settings().workflow_execution_timeout_seconds}s)"
                )

            # Check cycle detection
            can_execute, error_msg = context.can_execute_node(current_node_id)
            if not can_execute:
                if "Max steps" in (error_msg or ""):
                    raise MaxStepsExceededError(error_msg)
                else:
                    raise NodeExecutionLimitError(error_msg)

            # Get node instance
            node = self._node_registry.get_node(context.workflow.nodes, current_node_id)

            # Get node config; keep the raw type string (works for plugin types too).
            node_config = next(n for n in context.workflow.nodes if n["id"] == current_node_id)
            node_type_str = node_config["type"]

            # Prepare NodeInput via capability hook: START reads workflow_input,
            # all other nodes read the previous node's output.
            if node.input_source == "workflow_input":
                node_data = context.input_data
            else:
                node_data = previous_output if previous_output else {}

            node_input = NodeInput(data=node_data, context=context)

            # Save state before execution for logging; step id is the current counter.
            state_before = context.state.copy()
            step_start = datetime.now()
            assigned_step = context.step_number

            await self._node_runner.emit_start(
                context,
                node_id=current_node_id,
                node_type=node_type_str,
                node_data=node_data,
                state_before=state_before,
                project_state_before=context.project_state.copy(),
                step_number=assigned_step,
            )

            try:
                node_output = await self._node_runner.run(
                    node, node_input, node_id=current_node_id, step_number=assigned_step
                )
            except Exception as e:
                from assemblix_api.execution.exceptions import NodeExecutionError

                await self._node_runner.record_failed(
                    context,
                    node_id=current_node_id,
                    node_type=node_type_str,
                    node_data=node_data,
                    state_before=state_before,
                    step_number=assigned_step,
                    started_at=step_start,
                    error=e,
                )
                raise NodeExecutionError(e, current_node_id) from e

            # Apply outputs, emit events, log the COMPLETED step, checkpoint.
            context = await self._node_runner.record_completed(
                context,
                node_id=current_node_id,
                node_type=node_type_str,
                node_data=node_data,
                node_output=node_output,
                state_before=state_before,
                step_number=assigned_step,
                started_at=step_start,
            )

            # Increment step_number for the next iteration (AFTER logging).
            context = context.with_node_visited(current_node_id)

            # Check if this is a terminal node (capability hook replaces NodeType.END check).
            if node.is_terminal:
                # Extract metadata flags
                is_session_end = False
                is_error = False
                error_message = ""
                filtered_state = None
                filtered_project_state = None

                if node_output.metadata:
                    is_session_end = node_output.metadata.get("is_session_end", False)
                    is_error = node_output.metadata.get("is_error", False)
                    error_message = node_output.metadata.get("error_message", "")
                    filtered_state = node_output.metadata.get("filtered_state")
                    filtered_project_state = node_output.metadata.get("filtered_project_state")

                # Use filtered states if provided by END node
                final_state = filtered_state if filtered_state is not None else context.state
                final_project_state = (
                    filtered_project_state
                    if filtered_project_state is not None
                    else context.project_state
                )

                # Update context with filtered states
                from dataclasses import replace

                context = replace(
                    context,
                    state=final_state,
                    project_state=final_project_state,
                )

                # Return output, context, and all flags
                return (
                    node_output.data,
                    context,
                    is_session_end,
                    is_error,
                    error_message,
                )

            # Find next node; capability hook provides branch index for routing nodes.
            source_handle_index = node.get_branch_index(node_output)

            next_node_id = self._navigator.find_next_node(
                context.workflow.edges,
                context.workflow.nodes,
                current_node_id,
                source_handle_index,
            )

            if next_node_id is None:
                raise NoNextNodeError(f"No next node found from {current_node_id}")

            # Update for next iteration
            current_node_id = next_node_id
            previous_output = node_output.data

    async def _run_branch(
        self,
        node: BaseNode,
        node_data: dict,
        base_context: ExecutionContext,
        *,
        node_id: str,
        step_number: int,
    ) -> NodeOutput:
        """Run one node body inside its own branch session (parallel engine only).

        The branch scope gives the node a session-bound service bundle so concurrent
        branches never share a session. Outputs return to the main loop, which folds
        them into the shared context and logs the step on the run session (serially).
        """
        async with self._branch_scope(base_context) as branch_context:
            node_input = NodeInput(data=node_data, context=branch_context)
            return await self._node_runner.run(
                node, node_input, node_id=node_id, step_number=step_number
            )

    async def _execution_loop_parallel(
        self,
        context: ExecutionContext,
    ) -> tuple[dict, ExecutionContext, bool, bool, str]:
        """Parallel fork/join engine (dead-path elimination via DagScheduler).

        Ready nodes run concurrently as asyncio tasks; completions are processed one at a
        time (asyncio is single-threaded), so shared-context updates, step numbering and
        step logging stay race-free. State merges are last-write-wins by completion order.
        The run finishes only when every live branch is done — an END does not abort its
        siblings; the FIRST END reached provides the final output and session/error flags.
        Per-node processing mirrors _execution_loop_sequential exactly.
        """
        import asyncio
        from dataclasses import replace

        from assemblix_api.execution.dag_scheduler import DagScheduler
        from assemblix_api.execution.exceptions import (
            MaxStepsExceededError,
            NodeExecutionError,
            NodeExecutionLimitError,
            WorkflowTimeoutError,
        )

        settings = get_settings()
        execution_deadline = time.monotonic() + settings.workflow_execution_timeout_seconds

        start_node_id = self._navigator.find_start_node(context.workflow.nodes)
        scheduler = DagScheduler(context.workflow.nodes, context.workflow.edges, start_node_id)

        # First END wins: captured output + flags for the final result.
        final_output: dict = {}
        is_session_end = False
        is_error = False
        error_message = ""
        end_captured = False

        # In-flight tasks → metadata captured at launch.
        running: dict[asyncio.Task, dict] = {}

        async def _cancel_running() -> None:
            for t in running:
                t.cancel()
            if running:
                await asyncio.gather(*running, return_exceptions=True)
            running.clear()

        ready = scheduler.start()
        try:
            while ready or running:
                # 1. Launch every ready node. Counters (step_number, node_execution_count)
                #    are bumped synchronously per node, so each launch gets a unique step
                #    id and the cycle cap counts launches — no await in between.
                for ready_node in ready:
                    node_id = ready_node.node_id

                    can_execute, err_msg = context.can_execute_node(node_id)
                    if not can_execute:
                        if "Max steps" in (err_msg or ""):
                            raise MaxStepsExceededError(err_msg)
                        raise NodeExecutionLimitError(err_msg)

                    node = self._node_registry.get_node(context.workflow.nodes, node_id)
                    node_config = next(n for n in context.workflow.nodes if n["id"] == node_id)
                    node_type_str = node_config["type"]

                    if node.input_source == "workflow_input":
                        node_data = context.input_data
                    else:
                        node_data = ready_node.input_data or {}

                    state_before = context.state.copy()
                    project_state_before = context.project_state.copy()
                    assigned_step = context.step_number
                    started_at = datetime.now()

                    # Reserve this run's step id / cycle-cap slot.
                    context = context.with_node_visited(node_id)

                    await self._node_runner.emit_start(
                        context,
                        node_id=node_id,
                        node_type=node_type_str,
                        node_data=node_data,
                        state_before=state_before,
                        project_state_before=project_state_before,
                        step_number=assigned_step,
                    )

                    task = asyncio.create_task(
                        self._run_branch(
                            node,
                            node_data,
                            context,
                            node_id=node_id,
                            step_number=assigned_step,
                        )
                    )
                    running[task] = {
                        "node_id": node_id,
                        "node_type": node_type_str,
                        "node_data": node_data,
                        "state_before": state_before,
                        "assigned_step": assigned_step,
                        "started_at": started_at,
                        "node": node,
                    }
                ready = []

                if not running:
                    break

                # 2. Wait for the next node to finish (bounded by the global deadline).
                remaining = execution_deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkflowTimeoutError(
                        "Workflow execution exceeded the global time budget "
                        f"({settings.workflow_execution_timeout_seconds}s)"
                    )
                done, _pending = await asyncio.wait(
                    running.keys(),
                    timeout=remaining,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    raise WorkflowTimeoutError(
                        "Workflow execution exceeded the global time budget "
                        f"({settings.workflow_execution_timeout_seconds}s)"
                    )

                # 3. Process each finished node serially (no interleaving of the shared
                #    context updates and step logging).
                for task in done:
                    pend = running.pop(task)
                    node_id = pend["node_id"]
                    node_type_str = pend["node_type"]
                    node_data = pend["node_data"]
                    state_before = pend["state_before"]
                    assigned_step = pend["assigned_step"]
                    started_at = pend["started_at"]
                    node = pend["node"]

                    try:
                        node_output = task.result()
                    except Exception as e:
                        # A node error fails the whole run, as on the sequential path.
                        await self._node_runner.record_failed(
                            context,
                            node_id=node_id,
                            node_type=node_type_str,
                            node_data=node_data,
                            state_before=state_before,
                            step_number=assigned_step,
                            started_at=started_at,
                            error=e,
                        )
                        raise NodeExecutionError(e, node_id) from e

                    # Record the step and fold outputs into the shared context (serially).
                    context = await self._node_runner.record_completed(
                        context,
                        node_id=node_id,
                        node_type=node_type_str,
                        node_data=node_data,
                        node_output=node_output,
                        state_before=state_before,
                        step_number=assigned_step,
                        started_at=started_at,
                    )

                    # --- routing ---
                    if node.is_terminal:
                        if not end_captured:
                            end_captured = True
                            meta = node_output.metadata or {}
                            is_session_end = meta.get("is_session_end", False)
                            is_error = meta.get("is_error", False)
                            error_message = meta.get("error_message", "")
                            final_output = node_output.data
                            filtered_state = meta.get("filtered_state")
                            filtered_project_state = meta.get("filtered_project_state")
                            if filtered_state is not None:
                                context = replace(context, state=filtered_state)
                            if filtered_project_state is not None:
                                context = replace(context, project_state=filtered_project_state)
                        # END has no successors; siblings keep running until all finish.
                        continue

                    branch_index = node.get_branch_index(node_output)
                    result = scheduler.complete(
                        node_id, node_output.data, branch_index=branch_index
                    )
                    # A non-terminal node with no live successor just ends its branch —
                    # a leaf that, e.g., writes state and stops. Unlike the sequential
                    # engine this is NOT an error: sibling branches keep running and the
                    # run completes when all are exhausted (wait-all guarantees the leaf's
                    # state writes are already applied). NoNextNodeError stays a fatal
                    # error only on the single-path sequential engine.
                    if result.live_out_count == 0:
                        logger.info(
                            "workflow.branch.leaf",
                            node_id=node_id,
                            node_type=node_type_str,
                        )
                    ready.extend(result.ready)
        except BaseException:
            # Never leave orphaned node tasks running on abort (error/timeout/cap).
            await _cancel_running()
            raise

        return final_output, context, is_session_end, is_error, error_message

    async def _finalization_phase(
        self,
        execution: Execution,
        context: ExecutionContext,
        final_output: dict,
        is_session_end: bool = False,
        is_error: bool = False,
        error_message: str = "",
    ) -> None:
        """
        Save state and update execution.

        Steps:
        1. Deduct credits (total_credits comes from here)
        2. Save final state to ChatSession (if stateful)
        3. Save project state to ClientSession (if client_id)
        4. Save user + assistant messages (if stateful)
        5. Update execution status (COMPLETED or ERROR)
        6. End session if requested
        """
        # 1. Deduct credits FIRST to get total_credits for saving
        from decimal import Decimal

        from assemblix_api.enums import ExecutionStatus, MessageRole

        total_credits = Decimal("0")
        if context.organization_id:
            billing_result = await self._credit_service.deduct_for_execution(
                organization_id=context.organization_id,
                execution_id=execution.id,
                system_key_cost_usd=context.system_key_cost_usd,
                own_key_cost_usd=context.own_key_cost_usd,
                system_voice_cost_usd=context.system_voice_cost_usd,
                own_voice_cost_usd=context.own_voice_cost_usd,
                metadata={
                    "steps_count": context.step_number,
                },
            )
            total_credits = billing_result["total_credits"]

        # 2. Save final state to ChatSession (if stateful)
        if context.chat_session_id:
            await self._chat_service.update_session_state(
                session_id=context.chat_session_id,
                state_updates=context.state,
            )

        # 3. Save project state to ClientSession (if client_id)
        if context.client_session_id:
            await self._client_session_service.update_state(
                session_id=context.client_session_id,
                state_updates=context.project_state,
            )
            # Update execution stats in ClientSession
            await self._client_session_service.increment_execution_stats(
                session_id=context.client_session_id,
                credits=total_credits,
            )

        # 4. Save chat messages (if stateful).
        # Both user and assistant are persisted here so the DB stays consistent
        # with what nodes saw in-memory via context.chat_history. On a failed
        # execution (handled in _handle_error) nothing is persisted.
        if context.chat_session_id:
            user_message = context.input_data.get("message", "")
            if user_message:
                await self._chat_message_service.save_message(
                    chat_session_id=context.chat_session_id,
                    role=MessageRole.USER,
                    content=user_message,
                )

            # Persist the same (filtered) assistant turn that downstream agents saw
            # in-memory, so save_to_history / history_field also apply to the stored
            # session history. Fall back to the full output when no agent contributed
            # to the shared history this run.
            assistant_message = (
                context.last_history_message
                if context.last_history_message is not None
                else final_output.get("message", "")
            )
            if assistant_message:
                await self._chat_message_service.save_message(
                    chat_session_id=context.chat_session_id,
                    role=MessageRole.ASSISTANT,
                    content=assistant_message,
                    execution_id=execution.id,
                    metadata={
                        "credits": float(total_credits),  # Decimal -> float for JSON
                    },
                )

        # 5. Update execution status (COMPLETED or ERROR)
        status = ExecutionStatus.ERROR if is_error else ExecutionStatus.COMPLETED

        # Audio rides the live response / SSE only — keep it out of the DB.
        persisted_output = final_output
        if isinstance(final_output, dict) and "audio" in final_output:
            persisted_output = {k: v for k, v in final_output.items() if k != "audio"}

        await self._execution_service.update_execution_status(
            execution_id=execution.id,
            status=status,
            final_state=context.state,
            output=persisted_output,
            final_project_state=context.project_state,
            is_session_closed=is_session_end,
            total_credits=total_credits,
            own_key_cost_usd=context.own_key_cost_usd,
            steps_count=context.step_number,
            error_message=error_message if is_error else None,
        )

        # 6. End session if requested
        if is_session_end and context.chat_session_id:
            await self._chat_service.end_session(context.chat_session_id)

        # 7. Emit execution_complete event for debug mode
        if self._debug_event_manager.is_streaming(execution.id):
            debug_status = "error" if is_error else "completed"
            await self._debug_event_manager.emit_execution_complete(
                execution_id=execution.id,
                status=debug_status,
                output=final_output,
                final_state=context.state,
                final_project_state=context.project_state,
                total_steps=context.step_number,
                total_credits=total_credits,
                duration_ms=execution.duration_ms or 0,
                session_id=context.chat_session_id,
                own_key_cost_usd=context.own_key_cost_usd,
                is_session_closed=is_session_end,
            )
            # Drop the stream buffer a TTL later, so a late/reconnecting subscriber can
            # still replay the completed run before falling back to task polling.
            self._debug_event_manager.schedule_stream_cleanup(execution.id)

    @staticmethod
    def _resolve_node_type(workflow, node_id: str) -> str:
        """Look up a node's type from the workflow definition; default to set_variable-like fallback."""
        for n in workflow.nodes:
            if n.get("id") == node_id:
                return str(n.get("type", "unknown"))
        return "unknown"

    async def _handle_error(
        self,
        execution: Execution,
        context: ExecutionContext,
        error: Exception,
        failed_node_id: str | None = None,
    ) -> ExecutionResult:
        """
        Handle execution errors.

        Steps:
        1. Categorize error type
        2. Update execution as failed
        3. Return ExecutionResult with error informat ion

        Args:
            execution: Execution instance
            context: Execution context
            error: Exception that occurred
            failed_node_id: ID of node where error occurred

        Returns:
            ExecutionResult with status="failed" and error details
        """
        from assemblix_api.core.cel_evaluator import CELEvaluationError
        from assemblix_api.core.node_registry import NodeNotFoundError
        from assemblix_api.enums import (
            ExecutionErrorType,
            ExecutionStatus,
            StepStatus,
        )
        from assemblix_api.execution.exceptions import (
            MaxStepsExceededError,
            NodeExecutionLimitError,
        )

        # 1. Categorize error
        if isinstance(error, (MaxStepsExceededError, NodeExecutionLimitError)):
            error_type = ExecutionErrorType.CYCLE_DETECTION
        elif isinstance(error, CELEvaluationError):
            error_type = ExecutionErrorType.CONFIGURATION_ERROR
        elif isinstance(error, NodeNotFoundError):
            error_type = ExecutionErrorType.LOGIC_ERROR
        else:
            error_type = ExecutionErrorType.RUNTIME_ERROR

        # 2. Update execution as failed (may fail if session is in PendingRollback state)
        try:
            await self._execution_service.update_execution_status(
                execution_id=execution.id,
                status=ExecutionStatus.FAILED,
                error_message=str(error),
                error_type=error_type,
                failed_node_id=failed_node_id,
                final_state=context.state,  # Save partial state
                output={},
                final_project_state=context.project_state,
                steps_count=context.step_number,
            )
        except Exception as db_error:
            # Log but don't fail - we still need to send error event to client
            logger.exception("execution.status_update_failed", error=str(db_error))

        # 2.5. Fallback: ensure a FAILED ExecutionStep exists for the failed node.
        # The in-loop try/except already logs failures inside node.execute(),
        # but errors raised BEFORE node execution (cycle limit, navigator,
        # registry lookup) skip that path — log them here instead.
        if failed_node_id is not None:
            try:
                already_logged = await self._tracer.has_step(
                    execution_id=execution.id,
                    step_number=context.step_number,
                )
                if not already_logged:
                    node_type_value = self._resolve_node_type(context.workflow, failed_node_id)
                    now = datetime.now()
                    await self._tracer.log_step(
                        ExecutionStepData(
                            execution_id=execution.id,
                            step_number=context.step_number,
                            node_id=failed_node_id,
                            node_type=node_type_value,
                            input_data={},
                            output_data=None,
                            state_before=context.state,
                            state_after=None,
                            status=StepStatus.FAILED.value,
                            started_at=now,
                            completed_at=now,
                            duration_ms=0,
                            error_message=str(error),
                            cel_evaluations=None,
                        )
                    )
            except Exception as log_err:
                logger.warning(
                    "workflow.step.fallback_log_failed",
                    node_id=failed_node_id,
                    error=str(log_err),
                )

        # 2.6. Emit error event for debug mode (ALWAYS, even if DB update failed)
        if self._debug_event_manager.is_streaming(execution.id):
            await self._debug_event_manager.emit_error(
                execution_id=execution.id,
                error_message=str(error),
                error_type=error_type.value,
                failed_node_id=failed_node_id,
                step_number=context.step_number,
            )
            # Drop the stream buffer a TTL later (see the success path above).
            self._debug_event_manager.schedule_stream_cleanup(execution.id)

        # 3. Return ExecutionResult with error information
        return ExecutionResult(
            execution_id=execution.id,
            status="failed",
            output={},
            final_state=context.state,
            final_project_state=context.project_state,
            metadata=ExecutionResultMetadata(
                total_credits=float(execution.total_credits or 0),
                steps_count=context.step_number,
                duration_ms=execution.duration_ms or 0,
                own_key_cost_usd=(
                    float(execution.own_key_cost_usd)
                    if execution.own_key_cost_usd is not None
                    else None
                ),
                error_message=str(error),
                error_type=error_type.value,
                failed_node_id=failed_node_id,
            ),
            session_id=context.chat_session_id,
        )

    async def _load_initial_state(
        self,
        workflow: Workflow,
        chat_session_id: UUID | None,
        client_session_id: UUID | None,
        custom_state: dict | None = None,
        custom_project_state: dict | None = None,
    ) -> tuple[dict, dict]:
        """
        Load workflow state and project state.

        Args:
            workflow: Workflow model
            chat_session_id: Optional chat session ID
            client_session_id: Optional client session ID
            custom_state: Optional custom state to merge with base state
            custom_project_state: Optional custom project state to merge with base project state

        Returns:
            Tuple of (workflow_state, project_state)
        """
        # 1. Load workflow state
        if chat_session_id:
            # Load from ChatSession
            session = await self._chat_service.get_by_id(chat_session_id)
            workflow_state = session.current_state.copy()
        else:
            # Build from workflow state_schema defaults
            from assemblix_api.schemas.workflow import WorkflowDefinition

            workflow_def = WorkflowDefinition.from_workflow(workflow)
            workflow_state = {}
            for var in workflow_def.state_schema:
                workflow_state[var.name] = var.default_value

        # 2. Merge with custom_state if provided (custom values have priority).
        #    Each value is coerced to the type declared in the schema.
        if custom_state:
            workflow_types = {
                var.get("name"): var.get("type")
                for var in (workflow.state or [])
                if isinstance(var, dict) and var.get("name")
            }
            self._merge_with_coercion(
                base=workflow_state,
                overrides=custom_state,
                types_by_name=workflow_types,
                scope="state",
                workflow_id=workflow.id,
            )

        # 3. Load project state
        project = None
        if client_session_id:
            # Load from ClientSession
            client_session = await self._client_session_service.get_by_id(client_session_id)
            project_state = client_session.state.copy()
        else:
            # Build from project state_schema defaults
            project = await self._project_service.get_by_id(workflow.project_id)
            project_state = {}
            for var in project.state_schema:
                project_state[var["name"]] = get_typed_default_value(var)

        # 4. Merge with custom_project_state if provided (custom values have priority).
        #    Coercion needs the project schema — load it if not loaded yet.
        if custom_project_state:
            if project is None:
                project = await self._project_service.get_by_id(workflow.project_id)
            project_types = {
                var.get("name"): var.get("type")
                for var in (project.state_schema or [])
                if isinstance(var, dict) and var.get("name")
            }
            self._merge_with_coercion(
                base=project_state,
                overrides=custom_project_state,
                types_by_name=project_types,
                scope="project_state",
                workflow_id=workflow.id,
            )

        return workflow_state, project_state

    @staticmethod
    def _merge_with_coercion(
        base: dict,
        overrides: dict,
        types_by_name: dict,
        scope: str,
        workflow_id: UUID,
    ) -> None:
        """Write overrides onto base, coercing values to the types in types_by_name.

        On a failed coercion the raw value is kept and a warning is logged. Keys
        not present in the schema are carried over as-is without a warning.
        """
        for name, raw_value in overrides.items():
            declared_type = types_by_name.get(name)
            if declared_type is None:
                base[name] = raw_value
                continue

            coerced, ok = coerce_to_type(raw_value, declared_type)
            if not ok:
                logger.warning(
                    "workflow.custom_override.coerce_failed",
                    scope=scope,
                    name=name,
                    raw_value=raw_value,
                    declared_type=declared_type,
                    workflow_id=str(workflow_id),
                )
            base[name] = coerced
