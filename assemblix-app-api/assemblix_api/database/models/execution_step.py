"""
ExecutionStep model (a single workflow execution step)
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assemblix_api.enums import StepStatus

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .execution import Execution


class ExecutionStep(UUIDMixin, TimestampMixin, Base):
    """
    Trace of a single execution step (one node). Full input/output/state
    snapshot for debugging.
    """

    __tablename__ = "execution_steps"

    # Ownership
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Step identification
    step_number: Mapped[int] = mapped_column(nullable=False)
    node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Data snapshots
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    state_before: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    state_after: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Execution info
    status: Mapped[StepStatus] = mapped_column(nullable=False, default=StepStatus.RUNNING)
    error_message: Mapped[str | None] = mapped_column(default=None)

    # Timing
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    duration_ms: Mapped[int] = mapped_column(default=0)

    # LLM metrics (optional - AgentNode only)
    tokens_used: Mapped[int | None] = mapped_column(default=None)
    cost: Mapped[float | None] = mapped_column(default=None)
    model_used: Mapped[str | None] = mapped_column(String(100), default=None)
    own_key_cost_usd: Mapped[float | None] = mapped_column(
        default=None, comment="Cost in USD when using own API key"
    )

    # Debug metadata (optional)
    cel_evaluations: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Relationships
    execution: Mapped["Execution"] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_execution_steps_execution_step", "execution_id", "step_number"),
        UniqueConstraint("execution_id", "step_number", name="uq_execution_step"),
    )
