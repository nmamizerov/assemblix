from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel

from .chat_message import ChatMessageResponse
from .workflow import WorkflowBaseResponse


class ChatSessionBaseResponse(DTOModel):
    """
    Base model for chat session lists.
    """

    id: UUID = Field(description="Unique identifier of the chat session")
    name: str | None = Field(description="Optional display name of the chat session")
    workflow_id: UUID = Field(description="ID of the workflow this chat session executes")
    token_id: UUID | None = Field(
        description="ID of the API token used, None for debug mode sessions"
    )
    total_credits: float = Field(description="Total credits consumed by this chat session")
    message_count: int = Field(description="Number of messages exchanged in this session")
    is_active: bool = Field(description="Whether the chat session is currently active")
    is_debug: bool = Field(description="Whether the session is running in debug mode")
    last_message_at: datetime | None = Field(
        description="Timestamp of the last message in the session"
    )
    created_at: datetime = Field(description="Timestamp when the chat session was created")
    updated_at: datetime = Field(description="Timestamp when the chat session was last updated")
    workflow: WorkflowBaseResponse = Field(description="Summary of the associated workflow")


class ChatSessionResponse(ChatSessionBaseResponse):
    """
    Full chat session information.
    """

    current_state: dict = Field(
        description="Current execution state of the chat session as a key-value map"
    )


class ChatSessionDetailResponse(ChatSessionResponse):
    """
    Detailed chat session information including message history.
    """

    messages: list[ChatMessageResponse] = Field(
        description="Ordered list of messages in this chat session"
    )
