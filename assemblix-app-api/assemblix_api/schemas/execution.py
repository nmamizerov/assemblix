"""Internal schemas used inside the workflow execution engine; not exposed via the API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from assemblix_api.dto.base import DTOModel


@dataclass(frozen=True)
class AudioInput:
    """Raw audio for the current turn. Runtime-only — never serialized."""

    bytes: bytes
    mime: str
    filename: str


async def _noop_checkpoint() -> None:
    """Default db_checkpoint: a no-op for paths that don't manage a long-lived
    execution session (API request scope, unit tests)."""
    return None


if TYPE_CHECKING:
    from assemblix_api.core.cel_evaluator import CELEvaluator
    from assemblix_api.core.template_evaluator import TemplateEvaluator
    from assemblix_api.enums import PlanTier
    from assemblix_api.execution.credential_resolver import CredentialResolver
    from assemblix_api.schemas.debug_events import AlignmentData
    from assemblix_api.schemas.workflow import WorkflowDefinition
    from assemblix_api.services.chat_message_service import ChatMessageService
    from assemblix_api.services.credentials_service import CredentialsService
    from assemblix_api.services.execution_trace_service import ExecutionTracerService
    from assemblix_api.services.knowledge_base_service import KnowledgeBaseService


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable workflow execution context, passed between nodes and updated via the
    with_* methods. Frozen so older context versions never mutate. `state` is exposed
    in expressions as `state.*` and `project_state` as `project.*`."""

    execution_id: UUID
    workflow_id: UUID
    project_id: UUID
    user_id: UUID | None
    workflow: WorkflowDefinition
    state: dict
    project_state: dict
    chat_session_id: UUID | None
    client_session_id: UUID | None
    input_data: dict
    step_number: int
    visited_nodes: list[str]
    node_execution_count: dict[str, int]
    max_steps: int = 100
    max_node_executions: int = 10
    cel_evaluator: CELEvaluator | None = None
    template_evaluator: TemplateEvaluator | None = None
    credential_service: CredentialsService | None = None
    credential_resolver: CredentialResolver | None = None
    chat_message_service: ChatMessageService | None = None
    execution_tracer_service: ExecutionTracerService | None = None
    knowledge_base_service: KnowledgeBaseService | None = None
    # Billing — cost tracked separately per key type.
    organization_id: UUID | None = None
    organization_plan: PlanTier | None = None
    # Raw cost on system keys; margin is applied when converting to credits.
    system_key_cost_usd: Decimal = Decimal("0")
    # Raw cost on own keys; not charged.
    own_key_cost_usd: Decimal = Decimal("0")
    # Voice (TTS) cost, tracked separately so it can be itemized as VOICE_USAGE.
    system_voice_cost_usd: Decimal = Decimal("0")
    own_voice_cost_usd: Decimal = Decimal("0")
    # True when the run was dispatched with request.stream — the per-node delta sink is only
    # built when this is set (the request-level gate; the node-level gate lives on the node).
    stream_enabled: bool = False
    # In-memory chat history (OpenAI format), built once in preparation phase.
    # Includes prior session messages (if continuing a session) plus the
    # current user message. Agent nodes read from here, not from the DB.
    chat_history: list[dict] = field(default_factory=list)
    # Content of the most recent message appended to the shared history this run
    # (the last agent's answer, already filtered by save_to_history/history_field).
    # Persisted as the assistant turn at finalization so the DB matches what
    # downstream agents saw in-memory. None → fall back to the full final output.
    last_history_message: str | None = None
    # Audio input for the current turn (e.g., voice from user). Runtime-only field,
    # not persisted or serialized. Used by agent nodes to process audio input.
    audio_input: AudioInput | None = None
    # Transaction boundary hook: commits the execution session and returns its
    # DB connection to the pool. Nodes call this right before a long external
    # await (LLM/HTTP) so a workflow does not hold a Postgres connection while
    # idle on the network. Wired to session.commit by build_executor; a no-op on
    # the API request / unit-test paths. See the executor's per-node checkpoint.
    db_checkpoint: Callable[[], Awaitable[None]] = _noop_checkpoint

    @property
    def templates(self) -> TemplateEvaluator:
        """Render `{{...}}` templates. Uses the pre-built evaluator from the
        preparation phase; if it is absent (e.g. in unit tests where only
        `cel_evaluator` is set) — builds one on the fly on top of `cel_evaluator`."""
        if self.template_evaluator is not None:
            return self.template_evaluator
        from assemblix_api.core.template_evaluator import TemplateEvaluator

        assert self.cel_evaluator is not None, "cel_evaluator required to render templates"
        return TemplateEvaluator(self.cel_evaluator)

    def with_state(self, updates: dict) -> ExecutionContext:
        return replace(
            self,
            state={**self.state, **updates},
        )

    def with_project_state(self, updates: dict) -> ExecutionContext:
        return replace(
            self,
            project_state={**self.project_state, **updates},
        )

    def with_chat_history(self, messages: list[dict]) -> ExecutionContext:
        """Append messages to the in-memory shared dialog history. Used mid-run so an
        agent's answer is visible to later agents that include chat history. Also
        remembers the last appended content so finalization persists the same
        (filtered) assistant turn to the DB."""
        last = messages[-1].get("content") if messages else self.last_history_message
        return replace(
            self,
            chat_history=[*self.chat_history, *messages],
            last_history_message=last,
        )

    def with_user_turn(self, content: str) -> ExecutionContext:
        """Append the current user turn to the in-memory dialog history WITHOUT
        changing last_history_message (that field is for the assistant reply the
        finalizer persists). Used by the transcribe node so a downstream agent sees
        the transcript as the user's message."""
        return replace(
            self, chat_history=[*self.chat_history, {"role": "user", "content": content}]
        )

    def with_node_visited(self, node_id: str) -> ExecutionContext:
        new_count = {**self.node_execution_count}
        new_count[node_id] = new_count.get(node_id, 0) + 1
        new_step_number = self.step_number + 1
        return replace(
            self,
            visited_nodes=[*self.visited_nodes, node_id],
            node_execution_count=new_count,
            step_number=new_step_number,
        )

    def can_execute_node(self, node_id: str) -> tuple[bool, str | None]:
        """Cycle protection: enforce max total steps and max executions per node."""
        if self.step_number >= self.max_steps:
            return False, f"Max steps {self.max_steps} reached"

        count = self.node_execution_count.get(node_id, 0)
        if count >= self.max_node_executions:
            return (
                False,
                f"Node {node_id} executed {count} times (max: {self.max_node_executions})",
            )

        return True, None


@dataclass
class NodeInput:
    data: dict
    context: ExecutionContext
    # Per-run delta sink, set by NodeRunner when the run streams; agent nodes forward it to
    # AgentRunner. None for non-streaming runs and for non-agent nodes.
    on_delta: Callable[[str], Awaitable[None]] | None = None
    # Per-run PCM audio sink for streaming voice; set by NodeRunner alongside on_delta.
    on_audio: Callable[[bytes, AlignmentData | None], Awaitable[None]] | None = None


@dataclass
class NodeOutput:
    # metadata for END nodes carries: filtered_state, filtered_project_state,
    # is_error, error_message, is_session_end.
    data: dict
    state_updates: dict | None = None
    project_updates: dict | None = None
    next_edge_id: str | None = None
    metadata: dict | None = None
    # A message to append to the shared dialog history (OpenAI format), applied by the
    # executor after the step. None → nothing is appended.
    history_append: dict | None = None
    # The current turn's user text, folded via ExecutionContext.with_user_turn (does NOT
    # touch last_history_message). Used by the transcribe node so a downstream text agent
    # reads the transcript as the user's message instead of an empty audio-run message.
    user_turn: str | None = None


class ExecutionResultMetadata(DTOModel):
    total_credits: float
    steps_count: int
    duration_ms: int
    own_key_cost_usd: float | None = None
    error_message: str | None = None
    error_type: str | None = None
    failed_node_id: str | None = None


class ExecutionResult(DTOModel):
    execution_id: UUID
    status: str
    output: dict
    final_state: dict
    final_project_state: dict
    metadata: ExecutionResultMetadata
    session_id: UUID | None = None
    is_session_closed: bool = False


class ExecutionStepData(DTOModel):
    """Data for logging a single execution step"""

    execution_id: UUID
    step_number: int
    node_id: str
    node_type: str
    input_data: dict
    output_data: dict | None
    state_before: dict
    state_after: dict | None
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int = 0
    error_message: str | None = None
    tokens_used: int | None = None
    cost: float | None = None
    model_used: str | None = None
    own_key_cost_usd: float | None = None
    cel_evaluations: dict | None = None
    # Exact messages sent to the LLM (agent nodes only); None for other node types.
    llm_request: list | None = None


@dataclass
class AgentExecutionResult:
    """
    Result of agent execution from AgentOrchestrator.

    This is the output of the orchestrator layer, containing all information
    about the agent's execution including tool calls, costs, and conversation history.
    """

    content: str
    parsed_content: dict | None  # Structured output if JSON/structured
    metadata: dict  # tokens, cost, iterations, tool_calls_count, etc.
    messages: list[dict]  # Full conversation history including tool calls
    tool_executions: list[dict]  # Detailed information about all tool calls
