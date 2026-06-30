"""
ClientSession model (client session for cross-workflow state)
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .execution import Execution
    from .project import Project


class ClientSession(UUIDMixin, TimestampMixin, Base):
    """
    Ties together calls to different workflows under one "client" or "process",
    holding project-level state shared across all workflows of a project.
    """

    __tablename__ = "client_sessions"

    # Ownership
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Client identifier (unique within a project)
    client_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Client identifier unique within a project",
    )

    # Persistent state (project-level variables preserved across workflows)
    state: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Project variable state",
    )

    # Client metadata
    meta_data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Client metadata",
    )

    # Statistics
    execution_count: Mapped[int] = mapped_column(
        default=0,
        comment="Number of workflow executions",
    )
    total_credits: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        default=0,
        nullable=False,
        comment="Total credits consumed",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        index=True,
        comment="Whether the session is active",
    )

    # Debug mode flag
    is_debug: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        index=True,
    )

    # Timestamps
    last_activity_at: Mapped[datetime | None] = mapped_column(
        default=None,
        comment="Timestamp of last activity",
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="client_sessions")
    executions: Mapped[list["Execution"]] = relationship(
        back_populates="client_session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "client_id",
            name="uq_client_session_project_client",
        ),
        Index("ix_client_sessions_project_client", "project_id", "client_id"),
        Index("ix_client_sessions_project_active", "project_id", "is_active"),
        Index("ix_client_sessions_last_activity", "last_activity_at"),
    )

    def __repr__(self) -> str:
        return f"<ClientSession(id={self.id}, client_id={self.client_id}, project_id={self.project_id})>"
