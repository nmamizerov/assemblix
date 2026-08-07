"""Voice Agent Service — business logic for realtime conversational agents."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.voice_agent import VoiceAgent
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.database.repositories.workflow_repository import WorkflowRepository
from assemblix_api.dto.requests.voice_agent import (
    VoiceAgentCreateRequest,
    VoiceAgentUpdateRequest,
)
from assemblix_api.external.voice.catalog import has_conversation_route
from assemblix_api.schemas.voice_agent import VoiceAgentConfig


class VoiceAgentService:
    def __init__(
        self,
        repository: VoiceAgentRepository,
        workflow_repository: WorkflowRepository,
    ):
        self._repository = repository
        self._workflow_repository = workflow_repository

    @staticmethod
    def _assert_conversation_model(config: VoiceAgentConfig) -> None:
        """The catalog is runtime data, so this cannot live in the Pydantic schema."""
        if not has_conversation_route(config.voice.provider, config.voice.model):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{config.voice.provider}/{config.voice.model} is not a conversation "
                    "(speech-to-speech) model"
                ),
            )

    async def _assert_hook_workflows_in_project(
        self, project_id: UUID, config: VoiceAgentConfig
    ) -> None:
        """Analysis hooks may only reference workflows from the agent's own project."""
        for field, workflow_id in (
            ("turnWorkflowId", config.turn_workflow_id),
            ("finalWorkflowId", config.final_workflow_id),
        ):
            if workflow_id is None:
                continue
            try:
                parsed = UUID(workflow_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} {workflow_id} is not a valid workflow id",
                ) from None
            if not await self._workflow_repository.check_project_owns_workflow(parsed, project_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} {workflow_id} does not belong to this project",
                )

    async def create_voice_agent(
        self,
        project_id: UUID,
        data: VoiceAgentCreateRequest,
    ) -> VoiceAgent:
        self._assert_conversation_model(data.config)
        await self._assert_hook_workflows_in_project(project_id, data.config)
        return await self._repository.create(
            project_id=project_id,
            name=data.name,
            description=data.description,
            config=data.config.model_dump(),
        )

    async def get_voice_agent(self, agent_id: UUID) -> VoiceAgent:
        agent = await self._repository.get_by_id(agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Voice agent {agent_id} not found",
            )
        return agent

    async def get_project_voice_agents(self, project_id: UUID) -> Sequence[VoiceAgent]:
        return await self._repository.get_by_project_id(project_id)

    async def update_voice_agent(
        self,
        agent_id: UUID,
        data: VoiceAgentUpdateRequest,
    ) -> VoiceAgent:
        agent = await self.get_voice_agent(agent_id)

        update_fields: dict = {}
        if data.name is not None:
            update_fields["name"] = data.name
        # description is nullable, so an explicit null must clear it — only an
        # omitted field leaves it untouched.
        if "description" in data.model_fields_set:
            update_fields["description"] = data.description
        if data.config is not None:
            self._assert_conversation_model(data.config)
            await self._assert_hook_workflows_in_project(agent.project_id, data.config)
            update_fields["config"] = data.config.model_dump()
        if data.is_active is not None:
            update_fields["is_active"] = data.is_active

        if not update_fields:
            return agent
        return await self._repository.update(agent, **update_fields)

    async def delete_voice_agent(self, agent_id: UUID) -> None:
        # Ensure it exists (raises 404) before deleting by ID.
        await self.get_voice_agent(agent_id)
        await self._repository.delete(agent_id)
