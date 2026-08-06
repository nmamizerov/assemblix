"""Voice Agent Service — business logic for realtime conversational agents."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.voice_agent import VoiceAgent
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.dto.requests.voice_agent import (
    VoiceAgentCreateRequest,
    VoiceAgentUpdateRequest,
)
from assemblix_api.external.voice.voice_catalog import has_conversation_route
from assemblix_api.schemas.voice_agent import VoiceAgentConfig


class VoiceAgentService:
    def __init__(self, repository: VoiceAgentRepository):
        self._repository = repository

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

    async def create_voice_agent(
        self,
        project_id: UUID,
        data: VoiceAgentCreateRequest,
    ) -> VoiceAgent:
        self._assert_conversation_model(data.config)
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
        if data.description is not None:
            update_fields["description"] = data.description
        if data.config is not None:
            self._assert_conversation_model(data.config)
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
