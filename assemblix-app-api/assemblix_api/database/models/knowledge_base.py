"""
Knowledge base model
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .knowledge_document import KnowledgeDocument
    from .project import Project


class KnowledgeBase(UUIDMixin, TimestampMixin, Base):
    """
    Project knowledge base. Holds metadata and references to documents; full
    document text lives in KnowledgeDocument.content. During AgentNode execution
    the entire content of attached knowledge bases is injected into the system
    prompt.
    """

    __tablename__ = "knowledge_bases"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    document_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_characters: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="knowledge_bases")
    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_knowledge_bases_project_id", "project_id"),
        Index("ix_knowledge_bases_project_id_created_at", "project_id", "created_at"),
    )
