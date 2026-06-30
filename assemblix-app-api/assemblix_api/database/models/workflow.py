"""
Workflow model
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .chat_session import ChatSession
    from .execution import Execution
    from .project import Project


class Workflow(UUIDMixin, TimestampMixin, Base):
    """
    Workflow definition: nodes and edges configuration (JSONB) plus deployment
    settings (webhook URLs).
    """

    __tablename__ = "workflows"

    # Ownership
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="assemblix",
        server_default="assemblix",
        nullable=False,
        index=True,
        comment="Source product: assemblix or chat",
    )

    # Publishing (versioning system)
    # NULL - this is a draft (editable)
    # not NULL - this is a published version (immutable copy)
    published_for_workflow_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    version: Mapped[int | None] = mapped_column(default=None, nullable=True)

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    # Workflow Definition (JSONB for flexibility)
    nodes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Structure: [
    #   {
    #     "id": "node_1",
    #     "type": "agent",
    #     "position": {"x": 100, "y": 200},
    #     "config": {
    #       "provider": "openai",
    #       "model": "gpt-4o",
    #       "system_prompt": "...",
    #       "temperature": 0.7,
    #       "max_tokens": 1000
    #     }
    #   }
    # ]

    edges: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Structure: [
    #   {
    #     "id": "edge_1",
    #     "source": "node_1",
    #     "target": "node_2",
    #     "condition": null  # or condition config for branching
    #   }
    # ]
    state: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Structure: [
    #   {
    #     "name": "node_1",
    #     "default_value": 0,
    #     "type": "number"
    #   }
    # ]
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Structure: {
    #   "max_execution_duration_sec": 300,  # timeout for the whole workflow
    #   "max_steps": 100,  # max steps (loop protection)
    #   "max_node_executions": 10,  # how many times one node may run
    #   "timeout_per_node_sec": 60,  # per-node timeout

    #   # Optional: future features
    #   "retry_on_error": false,  # retry on errors
    #   "async_mode": false,  # background execution
    # }

    # Deployment Settings
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    is_published: Mapped[bool] = mapped_column(default=False)
    is_template: Mapped[bool] = mapped_column(default=False)

    # Webhook Callback
    webhook_url: Mapped[str | None] = mapped_column(String(500), default=None)

    # Statistics (denormalized for performance)
    execution_count: Mapped[int] = mapped_column(default=0)
    avg_execution_time: Mapped[float] = mapped_column(default=0.0)  # seconds
    total_tokens_used: Mapped[int] = mapped_column(default=0)
    total_cost: Mapped[float] = mapped_column(default=0.0)  # USD

    # Timestamps (from TimestampMixin)
    last_executed_at: Mapped[datetime | None] = mapped_column(default=None)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="workflows")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    executions: Mapped[list["Execution"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    # Self-referential relationship for versions: one draft workflow can have
    # many published versions; a version's published_for_workflow_id points to
    # the draft's id. Uses cascade="all, delete" instead of "delete-orphan"
    # because this is a self-referential relationship.
    published_versions: Mapped[list["Workflow"]] = relationship(
        "Workflow",
        foreign_keys=[published_for_workflow_id],
        remote_side="Workflow.id",  # via string to avoid circular reference
        cascade="all, delete",
        passive_deletes=False,
    )

    __table_args__ = (
        Index("ix_workflows_project_id_created_at", "project_id", "created_at"),
        Index("ix_workflows_is_active", "is_active"),
        # GIN index for JSONB search
        Index("ix_workflows_nodes_gin", "nodes", postgresql_using="gin"),
        # Indexes for publishing
        Index("ix_workflows_published_for_workflow_id", "published_for_workflow_id"),
        Index(
            "ix_workflows_published_for_workflow_id_version",
            "published_for_workflow_id",
            "version",
        ),
    )
