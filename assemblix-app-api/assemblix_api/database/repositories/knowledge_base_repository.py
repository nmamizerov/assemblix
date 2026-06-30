"""
Knowledge Base repository
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.knowledge_base import KnowledgeBase
from assemblix_api.database.repositories.base_repository import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """Repository for the knowledge_bases table."""

    def __init__(self, session: AsyncSession):
        super().__init__(KnowledgeBase, session)

    async def get_by_project_id(self, project_id: UUID) -> Sequence[KnowledgeBase]:
        """Get all knowledge bases of a project, ordered by creation date."""
        stmt = (
            select(self._model)
            .where(self._model.project_id == project_id)
            .order_by(self._model.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
