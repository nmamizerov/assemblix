"""
Request DTOs for execution
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import ExecutionStatus


class ExecuteWorkflowRequest(DTOModel):
    input: dict = Field(
        description="Input data for the workflow. Typically contains a 'message' field with the user's message"
    )
    session_id: UUID | None = Field(
        default=None,
        description="Existing chat session ID to continue a stateful conversation. Mutually exclusive with create_session",
    )
    create_session: bool = Field(
        default=False,
        description="If true, creates a new chat session for this execution (for stateful workflows)",
    )
    state: dict | None = Field(
        default=None,
        description="Custom initial state variables merged with the workflow's default state. User-provided values take priority",
    )
    project_state: dict | None = Field(
        default=None,
        description="Custom initial project-level state merged with the default project state. User-provided values take priority",
    )
    client_id: str | None = Field(
        default=None,
        description="External client identifier for cross-workflow state persistence. Used to link sessions from the same end-user",
    )
    metadata: dict | None = Field(
        default=None,
        description="Arbitrary client metadata stored in the ClientSession record (e.g. user agent, IP, custom tags)",
    )
    session_name: str | None = Field(
        default=None,
        description="Human-readable name for the chat session. Used only when create_session is true or a new session is created",
    )
    task: bool = Field(
        default=False,
        description="If true, returns execution_id immediately without waiting for the result (async mode)",
    )
    stream: bool = Field(
        default=False,
        description="If true, stream text deltas from streamable agent nodes over SSE (subscribe via GET /executions/{id}/stream)",
    )
    audio_base64: str | None = Field(
        default=None,
        description="Inbound audio as base64 (alternative to multipart /execute/audio). START node must accept voice",
    )
    audio_mime: str | None = Field(
        default=None,
        description="MIME type of audioBase64 (e.g. 'audio/wav', 'audio/mpeg'). Defaults to audio/wav",
    )
    audio_filename: str | None = Field(
        default=None,
        description="Optional original filename for the base64 audio",
    )


class ExecutionFilters(DTOModel):
    workflow_id: UUID | None = Field(default=None, description="Filter executions by workflow ID")
    chat_session_id: UUID | None = Field(
        default=None, description="Filter executions by chat session ID"
    )
    client_session_id: UUID | None = Field(
        default=None, description="Filter executions by client session ID"
    )
    status: ExecutionStatus | None = Field(
        default=None,
        description="Filter by execution status (e.g. pending, running, completed, failed)",
    )
    date_from: datetime | None = Field(
        default=None,
        description="Include only executions started at or after this datetime (inclusive, ISO 8601 format)",
    )
    date_to: datetime | None = Field(
        default=None,
        description="Include only executions started at or before this datetime (inclusive, ISO 8601 format)",
    )
    include_debug: bool = Field(
        default=False,
        description="If true, include debug executions in the results. Defaults to false to exclude them",
    )
