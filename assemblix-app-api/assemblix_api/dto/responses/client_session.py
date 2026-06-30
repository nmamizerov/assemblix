"""
Response DTOs for client sessions
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class ClientSessionBaseResponse(DTOModel):
    """Base client session information."""

    id: UUID = Field(description="Unique identifier of the client session")
    project_id: UUID = Field(description="ID of the project this client session belongs to")
    client_id: str = Field(description="External client identifier provided by the caller")
    state: dict = Field(
        description="Current accumulated state of the client session as a key-value map"
    )
    metadata: dict = Field(description="Arbitrary metadata associated with the client session")
    execution_count: int = Field(description="Total number of workflow executions in this session")
    total_credits: float = Field(
        description="Total credits consumed across all executions in this session"
    )
    is_active: bool = Field(description="Whether the client session is currently active")
    last_activity_at: datetime | None = Field(
        description="Timestamp of the last activity in this session"
    )
    created_at: datetime = Field(description="Timestamp when the client session was created")
    updated_at: datetime = Field(description="Timestamp when the client session was last updated")


class ClientSessionWithExecutionsResponse(ClientSessionBaseResponse):
    """Client session with execution information."""

    executions_count: int = Field(description="Number of executions associated with this session")
    last_execution_at: datetime | None = Field(
        description="Timestamp of the most recent execution in this session"
    )
