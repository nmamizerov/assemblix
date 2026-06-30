"""
Knowledge Document repository
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.knowledge_document import KnowledgeDocument
from assemblix_api.database.repositories.base_repository import BaseRepository


class KnowledgeDocumentRepository(BaseRepository[KnowledgeDocument]):
    """Repository for the knowledge_documents table."""

    def __init__(self, session: AsyncSession):
        super().__init__(KnowledgeDocument, session)

    async def get_by_knowledge_base_id(
        self, knowledge_base_id: UUID
    ) -> Sequence[KnowledgeDocument]:
        """Get all documents of a knowledge base."""
        stmt = (
            select(self._model)
            .where(self._model.knowledge_base_id == knowledge_base_id)
            .order_by(self._model.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_content_hash(
        self, knowledge_base_id: UUID, content_hash: str
    ) -> KnowledgeDocument | None:
        """Find a document by content hash (for deduplication)."""
        stmt = select(self._model).where(
            self._model.knowledge_base_id == knowledge_base_id,
            self._model.content_hash == content_hash,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_content_by_kb_ids(self, kb_ids: list[UUID]) -> str:
        """Get the concatenated text of all documents from several knowledge bases.

        Documents are joined with a separator for better LLM consumption.
        """
        if not kb_ids:
            return ""

        stmt = (
            select(self._model.content, self._model.name, self._model.knowledge_base_id)
            .where(self._model.knowledge_base_id.in_(kb_ids))
            .order_by(self._model.knowledge_base_id, self._model.created_at.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        if not rows:
            return ""

        parts = []
        for row in rows:
            content, name, _ = row
            parts.append(f"[{name}]\n{content}")

        return "\n\n---\n\n".join(parts)
