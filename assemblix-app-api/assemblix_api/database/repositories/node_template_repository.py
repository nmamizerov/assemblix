"""NodeTemplate repository - database operations for node templates."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.node_template import NodeTemplate
from assemblix_api.database.repositories.base_repository import BaseRepository


class NodeTemplateRepository(BaseRepository[NodeTemplate]):
    """Repository for the node_templates table."""

    def __init__(self, session: AsyncSession):
        super().__init__(NodeTemplate, session)

    async def get_by_project_id(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[NodeTemplate]:
        """Get all templates of a project."""
        stmt = select(self._model).where(self._model.project_id == project_id)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def check_project_owns_template(self, template_id: UUID, project_id: UUID) -> bool:
        """Check that a template belongs to a project."""
        stmt = select(self._model).where(
            self._model.id == template_id, self._model.project_id == project_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
