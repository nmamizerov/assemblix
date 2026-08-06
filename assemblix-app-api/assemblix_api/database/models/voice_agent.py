"""Voice agent model (realtime conversational agent)."""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .project import Project


class VoiceAgent(UUIDMixin, TimestampMixin, Base):
    """A realtime conversational agent. Unlike a Workflow it has no graph: the
    conversation is driven by a speech-to-speech provider session, and workflows
    attach only as observational analysis hooks referenced from ``config``."""

    __tablename__ = "voice_agents"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    # Structure validated by schemas/voice_agent.py::VoiceAgentConfig
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    session_count: Mapped[int] = mapped_column(default=0, nullable=False)
    total_credits: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        default=0,
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="voice_agents")

    __table_args__ = (Index("ix_voice_agents_project_id_created_at", "project_id", "created_at"),)
