"""
ChatSession model (persistent context for stateful workflows)
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .api_key import APIKey
    from .chat_message import ChatMessage
    from .execution import Execution
    from .workflow import Workflow


class ChatSession(UUIDMixin, TimestampMixin, Base):
    """
    Long-lived context for stateful workflows (chatbots), holding persistent
    state across messages.
    """

    __tablename__ = "chat_sessions"

    # Ownership
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="API key used to create this chat session (null for debug mode)",
    )

    # Persistent state (preserved across executions)
    current_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Statistics
    message_count: Mapped[int] = mapped_column(default=0)
    total_credits: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        default=0,
        nullable=False,
        comment="Total credits consumed",
    )

    # Name
    name: Mapped[str | None] = mapped_column(nullable=True, default=None)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Debug mode flag
    is_debug: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        index=True,
    )

    # Timestamps
    last_message_at: Mapped[datetime | None] = mapped_column(default=None)

    # Relationships
    workflow: Mapped["Workflow"] = relationship(back_populates="chat_sessions")
    token: Mapped["APIKey"] = relationship()
    executions: Mapped[list["Execution"]] = relationship(
        back_populates="chat_session",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="chat_session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    __table_args__ = (
        Index("ix_chat_sessions_token_active", "token_id", "is_active"),
        Index("ix_chat_sessions_workflow", "workflow_id"),
    )
