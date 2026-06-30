"""Project repository - database operations for projects."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.project import Project
from assemblix_api.database.repositories.base_repository import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for the projects table."""

    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)

    async def get_by_slug(self, organization_id: UUID, slug: str) -> Project | None:
        """Get a project by slug within an organization."""
        stmt = select(self._model).where(
            and_(
                self._model.organization_id == organization_id,
                self._model.slug == slug,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_organization_id(
        self,
        organization_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> Sequence[Project]:
        """Get all projects of an organization."""
        stmt = select(self._model).where(self._model.organization_id == organization_id)

        if is_active is not None:
            stmt = stmt.where(self._model.is_active == is_active)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def check_slug_exists_in_organization(self, organization_id: UUID, slug: str) -> bool:
        """Check whether a slug already exists within an organization."""
        result = await self.get_by_slug(organization_id, slug)
        return result is not None

    async def check_organization_owns_project(
        self, project_id: UUID, organization_id: UUID
    ) -> bool:
        """Check that a project belongs to an organization."""
        stmt = select(self._model).where(
            and_(
                self._model.id == project_id,
                self._model.organization_id == organization_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
