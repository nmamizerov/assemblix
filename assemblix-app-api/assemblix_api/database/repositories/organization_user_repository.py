"""OrganizationUser repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from assemblix_api.database.models.organization_user import OrganizationUser
from assemblix_api.database.repositories.base_repository import BaseRepository


class OrganizationUserRepository(BaseRepository[OrganizationUser]):
    """Repository for the organization_users table."""

    def __init__(self, session: AsyncSession):
        super().__init__(OrganizationUser, session)

    async def get_by_org_and_user(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationUser | None:
        """Return the membership record linking a user to an organization."""
        stmt = select(self._model).where(
            and_(
                self._model.organization_id == organization_id,
                self._model.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_organizations(
        self,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[OrganizationUser]:
        """Return a user's memberships with their organizations eager-loaded."""
        stmt = (
            select(self._model)
            .where(self._model.user_id == user_id)
            .options(joinedload(self._model.organization))
            .order_by(self._model.joined_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_organization_members(
        self,
        organization_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[OrganizationUser]:
        """Return an organization's members with their users eager-loaded."""
        stmt = (
            select(self._model)
            .where(self._model.organization_id == organization_id)
            .options(joinedload(self._model.user))
            .order_by(self._model.joined_at.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def is_user_in_organization(self, user_id: UUID, organization_id: UUID) -> bool:
        """Check whether the user is a member of the organization."""
        result = await self.get_by_org_and_user(organization_id, user_id)
        return result is not None

    async def is_user_owner(self, user_id: UUID, organization_id: UUID) -> bool:
        """Check whether the user is the owner of the organization."""
        result = await self.get_by_org_and_user(organization_id, user_id)
        return result is not None and result.is_owner
