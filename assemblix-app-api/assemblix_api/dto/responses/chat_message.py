"""
Response DTOs for chat messages
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import MessageRole


class ChatMessageResponse(DTOModel):
    """
    Chat message response model.
    """

    id: UUID = Field(description="Unique identifier of the chat message")
    chat_session_id: UUID = Field(description="ID of the chat session this message belongs to")
    execution_id: UUID | None = Field(
        description="ID of the workflow execution that produced this message, if any"
    )
    role: MessageRole = Field(description="Role of the message sender: 'user' or 'assistant'")
    content: str = Field(description="Text content of the message")
    meta_data: dict = Field(
        description="Additional metadata associated with the message (e.g. token usage, model info)"
    )
    created_at: datetime = Field(description="Timestamp when the message was created")
    updated_at: datetime = Field(description="Timestamp when the message was last updated")
