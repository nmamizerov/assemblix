"""Project service - business logic for projects."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from assemblix_api.database.models.project import Project
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.database.repositories.project_repository import ProjectRepository
from assemblix_api.services.base_service import BaseService

if TYPE_CHECKING:
    from assemblix_api.database.models.user import User
    from assemblix_api.dto.requests.project import ProjectCreateRequest


class ProjectService(BaseService[Project, ProjectRepository]):
    def __init__(
        self,
        repository: ProjectRepository,
        org_user_repository: OrganizationUserRepository,
    ):
        super().__init__(repository, entity_name="Project")
        self._org_user_repository = org_user_repository

    async def create_project(
        self,
        *,
        data: ProjectCreateRequest,
        organization_id: UUID,
        user: User,
    ) -> Project:
        """Create a new project; slug must be unique within the organization."""
        await self._verify_user_access(user, organization_id)

        project_data = data.model_dump()

        if not project_data.get("slug"):
            project_data["slug"] = (
                f"{project_data['name'].lower().replace(' ', '-')}-{str(uuid4())[:8]}"
            )

        if await self._repository.check_slug_exists_in_organization(
            organization_id, project_data["slug"]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Проект с slug '{project_data['slug']}' уже существует в этой организации",
            )

        project_data["organization_id"] = organization_id

        return await self.create(**project_data)

    async def update_project(
        self,
        project_id: UUID,
        user: User,
        **update_data,
    ) -> Project:
        """Update a project; a changed slug must stay unique within the organization."""
        project = await self.get_by_id(project_id)
        await self._verify_user_access(user, project.organization_id)

        if "slug" in update_data:
            new_slug = update_data["slug"]
            existing = await self._repository.get_by_slug(project.organization_id, new_slug)
            if existing and existing.id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Проект с slug '{new_slug}' уже существует в этой организации",
                )

        return await self.update(project_id, **update_data)

    async def delete_project(self, project_id: UUID, user: User) -> None:
        project = await self.get_by_id(project_id)
        await self._verify_user_access(user, project.organization_id)
        await self.delete(project_id)

    async def get_organization_projects(
        self,
        organization_id: UUID,
        user: User,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> Sequence[Project]:
        await self._verify_user_access(user, organization_id)

        return await self._repository.get_by_organization_id(
            organization_id,
            skip=skip,
            limit=limit,
            is_active=is_active,
        )

    async def verify_user_project_access(self, user: User, project_id: UUID) -> Project:
        """Verify the user can access the project (via its organization) and return it."""
        project = await self.get_by_id(project_id)
        await self._verify_user_access(user, project.organization_id)
        return project

    async def _verify_user_access(self, user: User, organization_id: UUID) -> None:
        # Admins have access to all organizations
        if user.is_admin:
            return

        if not await self._org_user_repository.is_user_in_organization(user.id, organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этой организации",
            )
