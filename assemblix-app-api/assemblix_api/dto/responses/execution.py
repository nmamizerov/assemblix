from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import (
    ExecutionErrorType,
    ExecutionStatus,
    StepStatus,
)


class ExecutionMetadata(DTOModel):
    total_steps: int = Field(description="Total number of steps executed in the workflow run")
    duration_ms: int = Field(description="Total execution duration in milliseconds")
    credits_used: float = Field(description="Number of platform credits consumed by this execution")
    own_key_cost_usd: float | None = Field(
        default=None,
        description="Cost in USD when the user's own API key was used for LLM calls",
    )


class ExecutionResponse(DTOModel):
    execution_id: UUID = Field(description="Unique identifier of this workflow execution")
    session_id: UUID | None = Field(
        default=None,
        description="Chat session ID if the workflow is running in stateful (session) mode",
    )
    output: dict = Field(description="Final output data produced by the workflow")
    state: dict = Field(description="Final workflow state after execution completes")
    status: str = Field(description="Execution result status, e.g. 'completed' or 'failed'")
    project_state: dict = Field(description="Final project-level state after execution completes")
    metadata: ExecutionMetadata = Field(
        description="Execution metadata including duration, steps count, and credits used"
    )
    is_session_closed: bool = Field(
        default=False,
        description="Whether the chat session was closed after this execution",
    )


class TaskExecutionResponse(DTOModel):
    """
    Returned immediately when running in task mode (task=True) or when the
    execution exceeds TASK_TIMEOUT_SECONDS.
    """

    execution_id: UUID = Field(
        description="Unique identifier of the launched execution, used for subsequent polling"
    )
    status: str = Field(
        default="running",
        description="Current execution status; always 'running' at creation time",
    )


class ExecutionErrorResponse(DTOModel):
    execution_id: UUID = Field(description="Unique identifier of the failed execution")
    status: Literal["failed"] = Field(
        description="Execution status; always 'failed' for error responses"
    )
    error: str = Field(description="Human-readable error message describing what went wrong")
    error_type: str = Field(
        description="Machine-readable error type classification, e.g. 'node_error', 'timeout'"
    )
    failed_node_id: str | None = Field(
        default=None,
        description="ID of the workflow node where the error occurred, if applicable",
    )
    partial_state: dict = Field(
        description="Partial workflow state captured at the moment the error occurred"
    )
    partial_project_state: dict = Field(
        description="Partial project-level state captured at the moment the error occurred"
    )


class ExecutionStepResponse(DTOModel):
    id: UUID = Field(description="Unique identifier of this execution step")
    execution_id: UUID = Field(description="ID of the parent workflow execution")
    step_number: int = Field(
        description="Sequential number of this step within the execution (1-based)"
    )
    node_id: str = Field(description="ID of the workflow node that was executed in this step")
    node_type: str = Field(
        description="Type of the executed node, e.g. 'agent', 'condition', 'http_request'"
    )
    input_data: dict = Field(description="Input data passed to the node for processing")
    output_data: dict | None = Field(description="Output data produced by the node after execution")
    state_before: dict = Field(
        description="Snapshot of the workflow state before this step executed"
    )
    state_after: dict | None = Field(
        description="Snapshot of the workflow state after this step executed"
    )
    status: StepStatus = Field(
        description="Execution status of this step, e.g. 'completed', 'failed', 'skipped'"
    )
    error_message: str | None = Field(default=None, description="Error message if the step failed")
    started_at: datetime = Field(description="Timestamp when this step started executing")
    completed_at: datetime | None = Field(description="Timestamp when this step finished executing")
    duration_ms: int = Field(description="Duration of this step in milliseconds")
    tokens_used: int | None = Field(
        default=None,
        description="Number of LLM tokens consumed by this step (applicable to agent nodes)",
    )
    cost: float | None = Field(
        default=None,
        description="Monetary cost of this step in platform credits (applicable to agent nodes)",
    )
    model_used: str | None = Field(
        default=None,
        description="LLM model identifier used for this step (applicable to agent nodes)",
    )
    own_key_cost_usd: float | None = Field(
        default=None,
        description="Cost in USD when the user's own API key was used for this step",
    )
    credits_used: float | None = Field(
        default=None, description="Number of platform credits consumed by this step"
    )
    cel_evaluations: dict | None = Field(
        default=None,
        description="CEL expression evaluation results for debugging condition and routing logic",
    )
    llm_request: list | None = Field(
        default=None,
        description="Exact messages sent to the LLM for this step (applicable to agent nodes)",
    )


class InFlightExecutionResponse(DTOModel):
    """
    Lightweight response for a single in-flight (QUEUED or RUNNING) execution.

    Only the fields needed for monitoring are returned — no per-step details
    (those are already available via the execution detail endpoint).

    Fields:
        id: Execution ID
        workflow_id: ID of the workflow being executed
        status: Current execution status (QUEUED or RUNNING)
        started_at: Execution start time; null for QUEUED rows that have not started yet
        steps_count: Number of steps completed so far
    """

    id: UUID = Field(description="Unique identifier of this execution record")
    workflow_id: UUID = Field(description="ID of the workflow being executed")
    status: ExecutionStatus = Field(description="Current execution status: QUEUED or RUNNING")
    started_at: datetime | None = Field(
        default=None,
        description=(
            "Execution start time; null for QUEUED rows that have not started yet. "
            "The service falls back to created_at so consumers always receive a usable timestamp."
        ),
    )
    steps_count: int = Field(description="Number of steps completed so far")


class ExecutionInfoResponse(DTOModel):
    """Execution information without per-step details."""

    id: UUID = Field(description="Unique identifier of this execution record")
    workflow_id: UUID = Field(description="ID of the workflow that was executed")
    chat_session_id: UUID | None = Field(
        default=None,
        description="ID of the associated chat session, if the workflow ran in stateful mode",
    )
    initial_state: dict = Field(description="Workflow state at the beginning of execution")
    final_state: dict | None = Field(
        description="Workflow state at the end of execution, null if execution is still running"
    )
    status: ExecutionStatus = Field(
        description="Current execution status: pending, running, completed, or failed"
    )
    is_debug: bool = Field(
        description="Whether this execution was run in debug mode with detailed step tracing"
    )
    error_message: str | None = Field(
        default=None, description="Human-readable error message if the execution failed"
    )
    error_type: ExecutionErrorType | None = Field(
        default=None,
        description="Machine-readable error type classification if the execution failed",
    )
    failed_node_id: str | None = Field(
        default=None, description="ID of the workflow node where the failure occurred"
    )
    started_at: datetime = Field(description="Timestamp when the execution started")
    completed_at: datetime | None = Field(
        description="Timestamp when the execution completed or failed"
    )
    duration_ms: int = Field(description="Total execution duration in milliseconds")
    total_credits: float = Field(
        description="Total number of platform credits consumed by this execution"
    )
    own_key_cost_usd: float | None = Field(
        default=None,
        description="Total cost in USD when the user's own API key was used",
    )
    steps_count: int = Field(description="Total number of steps executed in this run")
    meta_data: dict = Field(description="Arbitrary metadata associated with this execution")
    created_at: datetime = Field(description="Timestamp when this execution record was created")
    updated_at: datetime = Field(
        description="Timestamp when this execution record was last updated"
    )
    workflow: "WorkflowBaseResponse" = Field(
        description="Summary information about the executed workflow"
    )
    chat_session: Optional["ChatSessionBaseResponse"] = Field(
        default=None,
        description="Associated chat session details, if the workflow ran in stateful mode",
    )


class ExecutionDetailInfoResponse(ExecutionInfoResponse):
    """Detailed execution information including per-step execution traces."""

    workflow: "WorkflowResponse" = Field(
        description="Full workflow definition including nodes, edges, and state variables"
    )
    steps: list[ExecutionStepResponse] = Field(
        description="Ordered list of all execution steps with detailed trace information"
    )


# Import after model definitions to avoid circular imports
from assemblix_api.dto.responses.chat_session import (
    ChatSessionBaseResponse,
)  # noqa: E402
from assemblix_api.dto.responses.workflow import (
    WorkflowBaseResponse,
    WorkflowResponse,
)  # noqa: E402

# Rebuild models to resolve forward references
ExecutionInfoResponse.model_rebuild()
ExecutionDetailInfoResponse.model_rebuild()
