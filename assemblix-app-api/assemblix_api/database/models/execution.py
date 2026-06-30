"""
Execution model (a workflow run)
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assemblix_api.enums import ExecutionErrorType, ExecutionStatus

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .api_key import APIKey
    from .chat_session import ChatSession
    from .client_session import ClientSession
    from .execution_step import ExecutionStep
    from .workflow import Workflow


class Execution(UUIDMixin, TimestampMixin, Base):
    """
    A single workflow run from START to END. May be stateless (no chat) or
    stateful (within a chat session).
    """

    __tablename__ = "executions"

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
        comment="API key used to execute this workflow (null for debug mode)",
    )

    # Context (optional - for stateful workflows)
    chat_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )

    # Client Session (optional - for cross-workflow state)
    client_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("client_sessions.id", ondelete="SET NULL"),
        default=None,
        index=True,
        comment="Client session for project-level state across workflows",
    )

    # State snapshots
    initial_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    final_state: Mapped[dict | None] = mapped_column(JSONB, default=None)
    output: Mapped[dict | None] = mapped_column(
        JSONB,
        default=None,
        comment="Workflow output (output from the END node)",
        nullable=True,
    )

    # Execution status
    status: Mapped[ExecutionStatus] = mapped_column(
        nullable=False,
        default=ExecutionStatus.RUNNING,
        index=True,
    )

    # Debug mode flag
    is_debug: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        index=True,
    )

    # Error info
    error_message: Mapped[str | None] = mapped_column(default=None)
    error_type: Mapped[ExecutionErrorType | None] = mapped_column(default=None)
    failed_node_id: Mapped[str | None] = mapped_column(String(255), default=None)

    # Timing
    # Nullable: a QUEUED execution is pre-created by the queue tier (create_queued)
    # before any worker starts it, so started_at is unknown until mark_running backfills
    # it. A NOT NULL constraint here makes every queued run fail at INSERT.
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    duration_ms: Mapped[int] = mapped_column(default=0)

    # Metrics
    total_credits: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        default=0,
        nullable=False,
        comment="Total credits consumed (system keys with margin only)",
    )
    own_key_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8),
        default=None,
        nullable=True,
        comment="Total cost in USD when using own API keys",
    )
    steps_count: Mapped[int] = mapped_column(default=0)

    # Metadata
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    workflow: Mapped["Workflow"] = relationship(back_populates="executions")
    token: Mapped["APIKey"] = relationship()
    chat_session: Mapped[Optional["ChatSession"]] = relationship(back_populates="executions")
    client_session: Mapped[Optional["ClientSession"]] = relationship(back_populates="executions")
    steps: Mapped[list["ExecutionStep"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionStep.step_number",
    )

    __table_args__ = (
        Index("ix_executions_workflow_created", "workflow_id", "created_at"),
        Index("ix_executions_token_status", "token_id", "status"),
        Index("ix_executions_chat_session", "chat_session_id"),
        Index("ix_executions_client_session", "client_session_id"),
    )
