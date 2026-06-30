"""API key repository."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.api_key import APIKey

from .base_repository import BaseRepository


class APIKeyRepository(BaseRepository[APIKey]):
    """Repository for API keys."""

    def __init__(self, session: AsyncSession):
        super().__init__(APIKey, session)

    async def get_by_project_id(
        self,
        project_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> Sequence[APIKey]:
        """Return a project's API keys, excluding inactive ones by default."""
        stmt = select(APIKey).where(APIKey.project_id == project_id)

        if not include_inactive:
            stmt = stmt.where(APIKey.is_active == True)

        stmt = stmt.order_by(APIKey.created_at.desc())

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_prefix(self, prefix: str) -> APIKey | None:
        """Find an active API key by its prefix (e.g. "sk_a1b2c3d4")."""
        stmt = select(APIKey).where(
            and_(
                APIKey.prefix == prefix,
                APIKey.is_active == True,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_id(self, key_id: UUID) -> APIKey | None:
        """Return an active API key by ID, or None if not found/inactive."""
        stmt = select(APIKey).where(
            and_(
                APIKey.id == key_id,
                APIKey.is_active == True,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_usage(self, key_id: UUID) -> bool:
        """Increment request_count and refresh last_used_at for the key."""
        api_key = await self.get_by_id(key_id)
        if not api_key:
            return False

        api_key.request_count += 1
        api_key.last_used_at = datetime.utcnow()

        await self._session.flush()
        return True

    async def deactivate(self, key_id: UUID, project_id: UUID) -> bool:
        """
        Deactivate an API key (sets is_active=False instead of deleting, to
        preserve history). Returns False if not found or not owned by the project.
        """
        api_key = await self.get_by_id(key_id)
        if not api_key or api_key.project_id != project_id:
            return False

        api_key.is_active = False
        await self._session.flush()
        return True

    async def get_by_project_and_name(
        self,
        project_id: UUID,
        name: str,
    ) -> APIKey | None:
        """Find an active API key in a project by name."""
        stmt = select(APIKey).where(
            and_(
                APIKey.project_id == project_id,
                APIKey.name == name,
                APIKey.is_active == True,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
