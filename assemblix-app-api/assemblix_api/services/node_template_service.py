"""
NodeTemplate service - business logic for node templates.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.node_template import NodeTemplate
from assemblix_api.database.repositories.node_template_repository import (
    NodeTemplateRepository,
)
from assemblix_api.services.base_service import BaseService

if TYPE_CHECKING:
    from assemblix_api.dto.requests.node_template import (
        NodeTemplateCreateRequest,
        NodeTemplateUpdateRequest,
    )


class NodeTemplateService(BaseService[NodeTemplate, NodeTemplateRepository]):
    def __init__(
        self,
        repository: NodeTemplateRepository,
    ):
        super().__init__(repository, entity_name="NodeTemplate")

    async def create_node_template(
        self,
        *,
        project_id: UUID,
        data: NodeTemplateCreateRequest,
    ) -> NodeTemplate:
        template_data = data.model_dump()
        template_data["project_id"] = project_id

        return await self.create(**template_data)

    async def update_node_template(
        self,
        template_id: UUID,
        project_id: UUID,
        *,
        data: NodeTemplateUpdateRequest,
    ) -> NodeTemplate:
        await self._check_ownership(template_id, project_id)

        update_data = data.model_dump(
            exclude_unset=True,
            exclude={"id", "project_id", "created_at", "updated_at"},
        )

        return await self.update(template_id, **update_data)

    async def delete_node_template(self, template_id: UUID, project_id: UUID) -> None:
        await self._check_ownership(template_id, project_id)
        await self.delete(template_id)

    async def get_project_templates(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[NodeTemplate]:
        return await self._repository.get_by_project_id(
            project_id,
            skip=skip,
            limit=limit,
        )

    async def _check_ownership(self, template_id: UUID, project_id: UUID) -> NodeTemplate:
        """Ensure the template exists and belongs to the project, else raise 404/403."""
        template = await self._repository.get_by_id(template_id)

        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Шаблон не найден",
            )

        if template.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для работы с этим шаблоном",
            )

        return template
