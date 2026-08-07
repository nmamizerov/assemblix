"""Assembling everything a voice call needs before any audio flows.

A call is not a request/response run, so this service has no FastAPI dependency
chain to hang off. It is built explicitly by ``load_voice_session_setup`` below,
which owns a short-lived DB session: read the agent, its knowledge and its
provider key, then release the connection. A call lasts minutes and must not
occupy a pooled connection for that long.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.repositories.credentials_repository import CredentialsRepository
from assemblix_api.database.repositories.knowledge_base_repository import KnowledgeBaseRepository
from assemblix_api.database.repositories.knowledge_document_repository import (
    KnowledgeDocumentRepository,
)
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.database.repositories.project_repository import ProjectRepository
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.schemas.voice_agent import VoiceAgentConfig
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService


@dataclass(frozen=True)
class VoiceSessionSetup:
    """A call's inputs, resolved once so the runtime itself touches no database."""

    instructions: str
    voice: str
    language: str
    params: dict
    provider: str
    model: str
    api_key: str


class VoiceSessionService:
    def __init__(
        self,
        voice_agents: VoiceAgentRepository,
        projects: ProjectRepository,
        organizations: OrganizationRepository,
        knowledge_bases: KnowledgeBaseService,
        credentials: CredentialsService,
    ) -> None:
        self._voice_agents = voice_agents
        self._projects = projects
        self._organizations = organizations
        self._knowledge_bases = knowledge_bases
        self._credentials = credentials

    async def build_setup(self, *, voice_agent_id: UUID, project_id: UUID) -> VoiceSessionSetup:
        """Resolve the agent's configuration into what the runtime needs.

        Raises:
            HTTPException 404: the agent does not exist in this project.
        """
        agent = await self._voice_agents.get_by_id(voice_agent_id)
        if agent is None or agent.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice agent not found for this session",
            )

        config = VoiceAgentConfig(**agent.config)

        project = await self._projects.get_by_id(project_id)
        organization = (
            await self._organizations.get_by_id(project.organization_id) if project else None
        )
        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found for this session",
            )

        knowledge = ""
        if config.knowledge_base_ids:
            knowledge = await self._knowledge_bases.get_combined_content(
                [UUID(kb_id) for kb_id in config.knowledge_base_ids]
            )

        api_key, _ = await self._credentials.get_voice_api_key_with_fallback(
            credentials_id=UUID(config.voice.credential_id) if config.voice.credential_id else None,
            project_id=project_id,
            voice_provider=config.voice.provider,
            organization_plan=organization.plan,
        )

        return VoiceSessionSetup(
            instructions=self._build_instructions(config, knowledge),
            voice=config.voice.voice_id or "",
            language=config.language,
            params=config.params,
            provider=config.voice.provider,
            model=config.voice.model,
            api_key=api_key,
        )

    @staticmethod
    def _build_instructions(config: VoiceAgentConfig, knowledge: str) -> str:
        """Knowledge bases are inlined once, at session start — no retrieval mid-call."""
        parts = [instruction.content for instruction in config.instructions]
        if knowledge:
            parts.append(f"---\nБаза знаний:\n{knowledge}\n---")
        if config.first_message:
            parts.append(f"Начни разговор с фразы: {config.first_message}")
        return "\n\n".join(parts)


async def load_voice_session_setup(*, voice_agent_id: UUID, project_id: UUID) -> VoiceSessionSetup:
    """Composition root for the non-request path: open a DB session, resolve, release."""
    from assemblix_api.database import get_async_session

    async for session in get_async_session():
        service = VoiceSessionService(
            VoiceAgentRepository(session),
            ProjectRepository(session),
            OrganizationRepository(session),
            KnowledgeBaseService(
                KnowledgeBaseRepository(session), KnowledgeDocumentRepository(session)
            ),
            CredentialsService(CredentialsRepository(session), OrganizationUserRepository(session)),
        )
        return await service.build_setup(voice_agent_id=voice_agent_id, project_id=project_id)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No database session available",
    )
