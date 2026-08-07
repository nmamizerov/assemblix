"""Voice session model — one call against a voice agent."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .voice_agent import VoiceAgent


class VoiceSession(UUIDMixin, TimestampMixin, Base):
    """One conversation with a voice agent.

    Deliberately not a ``ChatSession``: that entity is bound to a ``workflow_id``
    and a voice agent has no workflow. The row is opened before the first audio
    frame — the analysis hooks need something to point their FK at — and closed
    once, at the end, with the transcript, duration and cost.
    """

    __tablename__ = "voice_sessions"

    voice_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("voice_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # [{role, text}] — assembled in process memory during the call, written once on close.
    transcript: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    total_credits: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        default=0,
        nullable=False,
    )
    # Provider token counts, kept for reconciling against an invoice. The charge is
    # computed from duration; these are observability, not billing.
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # v1 is editor-test only, so every session is a debug session.
    is_debug: Mapped[bool] = mapped_column(default=True, nullable=False)
    end_reason: Mapped[str | None] = mapped_column(String(50), default=None)

    voice_agent: Mapped["VoiceAgent"] = relationship(back_populates="sessions")

    __table_args__ = (Index("ix_voice_sessions_agent_started", "voice_agent_id", "started_at"),)
