"""Organization service - business logic for organizations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from assemblix_api.billing.plans import get_default_plan
from assemblix_api.database.models.organization import Organization
from assemblix_api.database.repositories.organization_repository import (
    OrganizationRepository,
)
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.dto.responses.organization import OrganizationMemberResponse
from assemblix_api.services.base_service import BaseService

if TYPE_CHECKING:
    from assemblix_api.database.models.user import User


class OrganizationService(BaseService[Organization, OrganizationRepository]):
    def __init__(
        self,
        repository: OrganizationRepository,
        org_user_repository: OrganizationUserRepository,
    ):
        super().__init__(repository, entity_name="Organization")
        self._org_user_repository = org_user_repository

    async def create_organization(
        self,
        *,
        name: str,
        slug: str | None,
        description: str | None,
        owner_id: UUID,
        is_personal: bool = False,
    ) -> Organization:
        """Create a new organization and register the owner as a member."""
        if not slug:
            slug = f"{name.lower().replace(' ', '-')}-{str(uuid4())[:8]}"

        if await self._repository.check_slug_exists(slug):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Организация с slug '{slug}' уже существует",
            )

        default_plan = get_default_plan()
        organization = await self.create(
            name=name,
            slug=slug,
            description=description,
            owner_id=owner_id,
            is_personal=is_personal,
            plan=default_plan,
            chat_plan=default_plan,
        )

        # Register the owner as a member of the organization
        await self._org_user_repository.create(
            organization_id=organization.id,
            user_id=owner_id,
            is_owner=True,
        )

        return organization

    async def get_user_organizations(
        self,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Organization]:
        org_users = await self._org_user_repository.get_user_organizations(
            user_id, skip=skip, limit=limit
        )
        return [ou.organization for ou in org_users]

    async def check_user_in_organization(self, user_id: UUID, organization_id: UUID) -> bool:
        return await self._org_user_repository.is_user_in_organization(user_id, organization_id)

    async def verify_user_access(self, user: User, organization_id: UUID) -> Organization:
        """Verify the user can access the organization and return it."""
        organization = await self.get_by_id(organization_id)

        # Admins have access to all organizations
        if user.is_admin:
            return organization

        if not await self.check_user_in_organization(user.id, organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этой организации",
            )

        return organization

    async def add_member(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        requester_id: UUID,
        is_owner: bool = False,
    ) -> None:
        """Add a member to the organization; only the owner may do this."""
        if not await self._org_user_repository.is_user_owner(requester_id, organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только владелец может добавлять участников",
            )

        if await self._org_user_repository.is_user_in_organization(user_id, organization_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь уже состоит в этой организации",
            )

        await self._org_user_repository.create(
            organization_id=organization_id,
            user_id=user_id,
            is_owner=is_owner,
        )

    async def remove_member(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        requester_id: UUID,
    ) -> None:
        """Remove a member; only the owner may do this and the owner cannot be removed."""
        if not await self._org_user_repository.is_user_owner(requester_id, organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только владелец может удалять участников",
            )

        if await self._org_user_repository.is_user_owner(user_id, organization_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя удалить владельца организации",
            )

        org_user = await self._org_user_repository.get_by_org_and_user(organization_id, user_id)
        if org_user:
            await self._org_user_repository.delete_instance(org_user)

    async def get_organization_members_with_details(
        self,
        organization_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[OrganizationMemberResponse]:
        org_users = await self._org_user_repository.get_organization_members(
            organization_id, skip=skip, limit=limit
        )

        members = []
        for org_user in org_users:
            member = OrganizationMemberResponse(
                id=org_user.user.id,
                user_id=org_user.user.id,
                email=org_user.user.email,
                full_name=org_user.user.full_name,
                is_owner=org_user.is_owner,
                joined_at=org_user.joined_at,
            )
            members.append(member)

        return members
