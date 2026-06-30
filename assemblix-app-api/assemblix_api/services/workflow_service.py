"""
Workflow service - business logic for workflows
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import inspect

from assemblix_api.database.models.workflow import Workflow
from assemblix_api.database.repositories.workflow_repository import WorkflowRepository
from assemblix_api.enums import NodeType
from assemblix_api.i18n.workflow_defaults import get_workflow_defaults
from assemblix_api.schemas import (
    AgentInstruction,
    AgentNode,
    AgentNodeConfig,
    AgentProvider,
    Edge,
    EndNode,
    EndNodeConfig,
    StartNode,
    StartNodeConfig,
)
from assemblix_api.services.base_service import BaseService

if TYPE_CHECKING:
    from assemblix_api.billing.service import BillingService
    from assemblix_api.dto.requests.workflow import (
        WorkflowCreateRequest,
        WorkflowUpdateRequest,
    )
    from assemblix_api.dto.responses.workflow import WorkflowResponse


def _create_default_workflow_structure(language: str = "en") -> dict:
    """Build the default workflow structure with 3 base nodes (START, AGENT, END)."""
    defaults = get_workflow_defaults(language)

    start_node_id = str(uuid4())
    agent_node_id = str(uuid4())
    end_node_id = str(uuid4())

    start_node = StartNode(
        id=start_node_id,
        type=NodeType.START,
        position={"x": 100, "y": 200},
        config=StartNodeConfig(),
    )

    agent_node = AgentNode(
        id=agent_node_id,
        type=NodeType.AGENT,
        position={"x": 400, "y": 200},
        config=AgentNodeConfig(
            name=defaults["agent_node_name"],
            provider=AgentProvider.OPENAI,
            model="gpt-4.1-nano",
            instructions=[
                AgentInstruction(
                    role="system",
                    content=defaults["agent_instruction"],
                )
            ],
            credential_id="",
        ),
    )

    # `properties={}` is an extra field allowed by DTOModel (extra="allow") and is
    # preserved in model_dump() output; mypy can't see it on EndNodeConfig.
    end_node_config = EndNodeConfig(name=defaults["end_node_name"], properties={})  # type: ignore[call-arg]
    end_node = EndNode(
        id=end_node_id,
        type=NodeType.END,
        position={"x": 700, "y": 200},
        config=end_node_config,
    )

    edge_start_agent = Edge(
        id=f"edge_{start_node_id}_{agent_node_id}",
        source=start_node_id,
        target=agent_node_id,
        source_handle=f"source_{start_node_id}_0",
        target_handle=f"target_{agent_node_id}_0",
    )

    edge_agent_end = Edge(
        id=f"edge_{agent_node_id}_{end_node_id}",
        source=agent_node_id,
        target=end_node_id,
        source_handle=f"source_{agent_node_id}_0",
        target_handle=f"target_{end_node_id}_0",
    )

    return {
        "nodes": [
            start_node.model_dump(),
            agent_node.model_dump(),
            end_node.model_dump(),
        ],
        "edges": [
            edge_start_agent.model_dump(),
            edge_agent_end.model_dump(),
        ],
    }


class WorkflowService(BaseService[Workflow, WorkflowRepository]):
    def __init__(
        self, repository: WorkflowRepository, billing_service: BillingService | None = None
    ):
        super().__init__(repository, entity_name="Workflow")
        self._billing_service = billing_service

    async def create_workflow(
        self,
        *,
        data: WorkflowCreateRequest,
        organization_id: UUID,
        language: str = "en",
        source: str = "assemblix",
    ) -> Workflow:
        if self._billing_service:
            await self._billing_service.check_can_create_workflow(organization_id, source=source)

        workflow_data = data.model_dump()

        # Empty nodes -> seed the localized default structure
        if not workflow_data.get("nodes"):
            default_structure = _create_default_workflow_structure(language)
            workflow_data["nodes"] = default_structure["nodes"]
            workflow_data["edges"] = default_structure["edges"]

        if not workflow_data.get("name"):
            workflow_data["name"] = get_workflow_defaults(language)["workflow_name"]

        workflow_data["source"] = source
        workflow_data["slug"] = str(uuid4())

        return await self.create(**workflow_data)

    async def update_workflow(
        self,
        workflow_id: UUID,
        project_id: UUID,
        *,
        data: WorkflowUpdateRequest,
    ) -> Workflow:
        await self._check_ownership(workflow_id, project_id)

        # Only explicitly-set fields; service fields are never updatable
        update_data = data.model_dump(
            exclude_unset=True,
            exclude={"id", "project_id", "slug", "created_at", "updated_at"},
        )

        return await self.update(workflow_id, **update_data)

    async def delete_workflow(self, workflow_id: UUID, project_id: UUID) -> None:
        await self._check_ownership(workflow_id, project_id)
        await self.delete(workflow_id)

    async def get_project_workflows(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
        is_published: bool | None = None,
        is_template: bool | None = None,
    ) -> Sequence[Workflow]:
        return await self._repository.get_by_project_id(
            project_id,
            skip=skip,
            limit=limit,
            is_active=is_active,
            is_published=is_published,
            is_template=is_template,
        )

    async def publish_workflow(self, workflow_id: UUID, project_id: UUID) -> Workflow:
        """Publish a workflow by creating an immutable copy as a new version."""
        draft_workflow = await self._check_ownership(workflow_id, project_id)

        # Only drafts can be published, not already-published versions
        if draft_workflow.published_for_workflow_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя публиковать уже опубликованную версию. Публикуйте только драфты.",
            )

        next_version = await self._repository.get_next_version(workflow_id)

        # Copy all model columns except identity, timestamps and stats, which are reset
        mapper = inspect(Workflow)
        excluded_columns = {
            "id",
            "slug",
            "created_at",
            "updated_at",
            "published_for_workflow_id",
            "version",
            "last_executed_at",
            "execution_count",
            "avg_execution_time",
            "total_tokens_used",
            "total_cost",
        }

        published_workflow_data = {
            col.key: getattr(draft_workflow, col.key)
            for col in mapper.columns
            if col.key not in excluded_columns
        }

        published_workflow_data.update(
            {
                "slug": str(uuid4()),
                "is_published": True,
                "published_for_workflow_id": workflow_id,
                "version": next_version,
                "last_executed_at": None,
                "execution_count": 0,
                "avg_execution_time": 0.0,
                "total_tokens_used": 0,
                "total_cost": 0.0,
            }
        )

        published_workflow = await self.create(**published_workflow_data)

        return published_workflow

    async def get_workflow_with_versions(self, workflow: Workflow) -> WorkflowResponse:
        from assemblix_api.dto.responses.workflow import (
            WorkflowResponse,
            WorkflowVersionInfo,
        )

        # Published versions are only attached for drafts
        versions = []
        if workflow.published_for_workflow_id is None:
            published_versions = await self._repository.get_published_versions(workflow.id)
            versions = [
                WorkflowVersionInfo.model_validate(v, from_attributes=True)
                for v in published_versions
            ]

        workflow_data = WorkflowResponse.model_validate(workflow, from_attributes=True)
        workflow_data.versions = versions

        return workflow_data

    async def copy_workflow(
        self, workflow_id: UUID, project_id: UUID, organization_id: UUID
    ) -> Workflow:
        """Create a copy of a workflow; the copy is always a fresh draft."""
        source_workflow = await self._check_ownership(workflow_id, project_id)

        if self._billing_service:
            await self._billing_service.check_can_create_workflow(organization_id)

        # Copy all model columns except identity, timestamps and stats, which are reset
        mapper = inspect(Workflow)
        excluded_columns = {
            "id",
            "slug",
            "created_at",
            "updated_at",
            "published_for_workflow_id",
            "version",
            "last_executed_at",
            "execution_count",
            "avg_execution_time",
            "total_tokens_used",
            "total_cost",
        }

        copied_workflow_data = {
            col.key: getattr(source_workflow, col.key)
            for col in mapper.columns
            if col.key not in excluded_columns
        }

        copied_workflow_data.update(
            {
                "slug": str(uuid4()),
                "name": f"{source_workflow.name} (копия)",
                "is_published": False,
                "published_for_workflow_id": None,
                "version": None,
                "last_executed_at": None,
                "execution_count": 0,
                "avg_execution_time": 0.0,
                "total_tokens_used": 0,
                "total_cost": 0.0,
            }
        )

        copied_workflow = await self.create(**copied_workflow_data)

        return copied_workflow

    async def move_workflow(
        self,
        workflow_id: UUID,
        source_project_id: UUID,
        target_project_id: UUID,
        target_organization_id: UUID,
    ) -> Workflow:
        """Move a draft and all its published versions to another project."""
        draft_workflow = await self._check_ownership(workflow_id, source_project_id)

        if draft_workflow.published_for_workflow_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя переносить опубликованную версию. Переносите только драфты.",
            )

        if self._billing_service:
            await self._billing_service.check_can_create_workflow(target_organization_id)

        await self._repository.move_to_project(workflow_id, target_project_id)

        return await self.get_by_id(workflow_id)

    async def get_latest_published(self, workflow_id: UUID) -> Workflow | None:
        return await self._repository.get_latest_published(workflow_id)

    async def _check_ownership(self, workflow_id: UUID, project_id: UUID) -> Workflow:
        """Return the workflow, raising 403 if it does not belong to the project."""
        workflow = await self.get_by_id(workflow_id)

        if workflow.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для работы с этим workflow",
            )

        return workflow
