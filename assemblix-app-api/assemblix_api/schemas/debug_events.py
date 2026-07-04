"""Schemas for debug events streamed to the client in real time via SSE."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from assemblix_api.dto.base import DTOModel


class DebugEventType(str, Enum):
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    EXECUTION_COMPLETE = "execution_complete"
    ERROR = "error"


class DebugEvent(DTOModel):
    """Debug-mode event streamed to the client in real time over SSE."""

    event_type: DebugEventType
    execution_id: UUID
    timestamp: datetime
    data: dict[str, Any]


class StepStartEventData(DTOModel):
    step_number: int
    node_id: str
    node_type: str
    input_data: dict[str, Any]
    state_before: dict[str, Any]
    project_state_before: dict[str, Any]


class StepCompleteEventData(DTOModel):
    step_number: int
    node_id: str
    node_type: str
    output_data: dict[str, Any] | None
    state_after: dict[str, Any]
    project_state_after: dict[str, Any]
    duration_ms: int
    model_used: str | None = None
    tokens_used: int | None = None
    cost: float | None = None
    own_key_cost_usd: float | None = None
    credits_used: float | None = None
    # Exact messages sent to the LLM (agent nodes only); None for other node types.
    llm_request: list[dict[str, Any]] | None = None


class ExecutionCompleteEventData(DTOModel):
    status: str
    output: dict[str, Any]
    final_state: dict[str, Any]
    final_project_state: dict[str, Any]
    total_steps: int
    total_credits: float
    duration_ms: int
    session_id: UUID | None = None
    own_key_cost_usd: float | None = None
    is_session_closed: bool = False


class ErrorEventData(DTOModel):
    error_message: str
    error_type: str
    failed_node_id: str | None = None
    step_number: int
