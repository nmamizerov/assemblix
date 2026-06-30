"""
Knowledge base document model
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .knowledge_base import KnowledgeBase


class KnowledgeDocument(UUIDMixin, TimestampMixin, Base):
    """
    Knowledge base document. Stores plain-text content (extracted from a PDF or
    entered manually). content_hash is used to prevent duplicate documents.
    """

    __tablename__ = "knowledge_documents"

    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # SHA256 hash of content for deduplication within a single KB
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")

    __table_args__ = (
        Index("ix_knowledge_documents_kb_id", "knowledge_base_id"),
        Index(
            "ix_knowledge_documents_kb_id_hash",
            "knowledge_base_id",
            "content_hash",
        ),
        Index(
            "ix_knowledge_documents_kb_id_created_at",
            "knowledge_base_id",
            "created_at",
        ),
    )
