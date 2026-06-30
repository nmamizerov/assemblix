"""
Project model
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .api_key import APIKey
    from .client_session import ClientSession
    from .credentials import Credentials
    from .knowledge_base import KnowledgeBase
    from .node_template import NodeTemplate
    from .notification_channel import NotificationChannel
    from .organization import Organization
    from .workflow import Workflow


class Project(UUIDMixin, TimestampMixin, Base):
    """
    Projects group workflows, credentials, and API keys within an organization.
    Each project belongs to a single organization.
    """

    __tablename__ = "projects"

    # Ownership
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization ID",
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Project name",
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="URL-friendly identifier (unique within an organization)",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        default=None,
        comment="Project description",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether the project is active",
    )

    # Project-level state schema (for ClientSession)
    state_schema: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Schema of project variables for ClientSession",
    )
    # Structure: [
    #   {
    #     "name": "user_name",
    #     "default_value": null,
    #     "type": "string"
    #   },
    #   {
    #     "name": "user_preferences",
    #     "default_value": {},
    #     "type": "object"
    #   }
    # ]

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="projects")
    workflows: Mapped[list["Workflow"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    credentials: Mapped[list["Credentials"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    client_sessions: Mapped[list["ClientSession"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    node_templates: Mapped[list["NodeTemplate"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    notification_channels: Mapped[list["NotificationChannel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_project_org_slug",
        ),
        Index("ix_projects_organization_id", "organization_id"),
        Index("ix_projects_slug", "slug"),
        Index("ix_projects_is_active", "is_active"),
        Index(
            "ix_projects_org_active",
            "organization_id",
            "is_active",
        ),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, slug={self.slug})>"
