"""Voice Agent REST API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from assemblix_api.api.rest._scope import resolve_project_id
from assemblix_api.core.auth_context import AuthContext
from assemblix_api.dependencies import (
    get_auth_context,
    get_project_service,
    get_voice_agent_service,
)
from assemblix_api.dto.requests.voice_agent import (
    VoiceAgentCreateRequest,
    VoiceAgentUpdateRequest,
)
from assemblix_api.dto.responses.voice_agent import VoiceAgentResponse
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.voice_agent_service import VoiceAgentService

router = APIRouter(prefix="/voice-agents", tags=["Voice Agents"])


@router.get("/", response_model=list[VoiceAgentResponse])
async def list_voice_agents(
    project_id: UUID | None = Query(
        None, description="Project ID; omit when using a project-scoped API key"
    ),
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
):
    effective_project_id = resolve_project_id(project_id, auth)
    await project_service.authorize_project_access(auth, effective_project_id)
    return await service.get_project_voice_agents(effective_project_id)


@router.get("/{agent_id}", response_model=VoiceAgentResponse)
async def get_voice_agent(
    agent_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
):
    agent = await service.get_voice_agent(agent_id)
    await project_service.authorize_project_access(auth, agent.project_id)
    return agent


@router.post("/", response_model=VoiceAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_agent(
    data: VoiceAgentCreateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
):
    data.project_id = resolve_project_id(data.project_id, auth)
    project = await project_service.authorize_project_access(auth, data.project_id)
    return await service.create_voice_agent(project_id=project.id, data=data)


@router.patch("/{agent_id}", response_model=VoiceAgentResponse)
async def update_voice_agent(
    agent_id: UUID,
    data: VoiceAgentUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
):
    agent = await service.get_voice_agent(agent_id)
    await project_service.authorize_project_access(auth, agent.project_id)
    return await service.update_voice_agent(agent_id=agent_id, data=data)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_agent(
    agent_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
):
    agent = await service.get_voice_agent(agent_id)
    await project_service.authorize_project_access(auth, agent.project_id)
    await service.delete_voice_agent(agent_id)
