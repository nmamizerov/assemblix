"""
Request DTOs for chat sessions.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import MessageRole


class ChatSessionFilters(DTOModel):
    """
    Filters for the chat sessions list.

    Fields:
        workflow_id: Filter by workflow
        include_debug: Include debug sessions (default False - excludes debug)
        date_from: Filter by last message date (>=)
        date_to: Filter by last message date (<=)
    """

    workflow_id: UUID | None = Field(
        default=None, description="Filter chat sessions by the workflow they belong to"
    )
    include_debug: bool = Field(
        default=False,
        description="If true, include debug sessions in the results. Defaults to false to exclude them",
    )
    date_from: datetime | None = Field(
        default=None,
        description="Include only sessions with the last message at or after this datetime (inclusive, ISO 8601)",
    )
    date_to: datetime | None = Field(
        default=None,
        description="Include only sessions with the last message at or before this datetime (inclusive, ISO 8601)",
    )


class ChatSessionUpdateNameRequest(DTOModel):
    """
    Request to rename a chat session.

    Fields:
        name: New session name
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="New human-readable name for the chat session, must be 1-255 characters",
    )


class SendMessageRequest(DTOModel):
    """
    Request to manually send a message to a chat session.

    Fields:
        content: Message text
        role: Sender role (default user)
        meta_data: Additional metadata (optional)
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Text content of the message, must be 1-50000 characters",
    )
    role: MessageRole = Field(
        default=MessageRole.USER,
        description="Role of the message sender: 'user', 'assistant', or 'system'. Defaults to 'user'",
    )
    meta_data: dict | None = Field(
        default=None,
        description="Optional arbitrary metadata attached to the message (e.g. source info, attachments)",
    )
