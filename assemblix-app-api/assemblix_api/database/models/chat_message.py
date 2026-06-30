"""
ChatMessage model (a single chat message)
"""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assemblix_api.enums import MessageRole

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .chat_session import ChatSession
    from .execution import Execution


class ChatMessage(UUIDMixin, TimestampMixin, Base):
    """
    A single message in a dialog (user/assistant/system), forming the chat
    history used as LLM context.
    """

    __tablename__ = "chat_messages"

    # Ownership
    chat_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"),
        default=None,
    )

    # Message data
    role: Mapped[MessageRole] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)

    # Metadata (e.g. model, tokens, etc.)
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    chat_session: Mapped["ChatSession"] = relationship(back_populates="messages")
    execution: Mapped[Optional["Execution"]] = relationship()

    __table_args__ = (Index("ix_chat_messages_session_created", "chat_session_id", "created_at"),)
