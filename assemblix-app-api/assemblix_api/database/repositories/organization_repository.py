"""Organization repository - database operations for organizations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.organization import Organization
from assemblix_api.database.repositories.base_repository import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for the organizations table."""

    def __init__(self, session: AsyncSession):
        super().__init__(Organization, session)

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Get an organization by slug."""
        stmt = select(self._model).where(self._model.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_owner_id(
        self,
        owner_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> Sequence[Organization]:
        """Get all organizations owned by a user."""
        stmt = select(self._model).where(self._model.owner_id == owner_id)

        if is_active is not None:
            stmt = stmt.where(self._model.is_active == is_active)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def check_slug_exists(self, slug: str) -> bool:
        """Check whether a slug already exists."""
        stmt = select(self._model).where(self._model.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
