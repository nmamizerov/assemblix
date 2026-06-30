"""
Node template model
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .project import Project


class NodeTemplate(UUIDMixin, TimestampMixin, Base):
    """
    Stores reusable node configurations with meaningful names. A template holds
    a node's full configuration (as one element of the workflow.nodes array).
    """

    __tablename__ = "node_templates"

    # Ownership
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    # Node Configuration
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Structure: full node configuration (one element from workflow.nodes)
    # {
    #   "id": "node_1",
    #   "type": "agent",
    #   "position": {"x": 100, "y": 200},
    #   "config": {
    #     "name": "Agent",
    #     "provider": "openai",
    #     "model": "gpt-4o",
    #     "instructions": [{"role": "system", "content": "..."}],
    #     ...
    #   }
    # }

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="node_templates")

    __table_args__ = (
        Index("ix_node_templates_project_id_created_at", "project_id", "created_at"),
        # GIN index for JSONB search on config
        Index("ix_node_templates_config_gin", "config", postgresql_using="gin"),
    )
