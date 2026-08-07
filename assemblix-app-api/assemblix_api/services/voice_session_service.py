"""Assembling everything a voice call needs, and recording what it did.

A call is not a request/response run, so this service has no FastAPI dependency
chain to hang off. It is built explicitly by the module-level functions below,
each of which owns a *short-lived* DB session: resolve, or write, then release.
A call lasts minutes and must not occupy a pooled connection for that long — so
the three moments that touch the database (setup, session opened, session closed)
are the only ones that ever hold one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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
from assemblix_api.database.repositories.voice_session_repository import VoiceSessionRepository
from assemblix_api.external.llm.provider_config import resolve_api_base
from assemblix_api.external.voice.catalog.registry import find_voice_model
from assemblix_api.schemas.voice_agent import VoiceAgentConfig
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService

logger = structlog.get_logger(__name__)

# Credit columns are Numeric(20, 8); anything finer is noise the column cannot hold.
_CREDITS_QUANTUM = Decimal("0.00000001")

# A call ends for one of a handful of reasons. Everything else — notably a provider's
# WebSocket close frame, which is prose and can be any length — is diagnostics, and is
# logged rather than written into a column other code branches on.
_END_REASONS = frozenset({"user_hangup", "timeout", "error", "completed", "closed"})


def normalize_end_reason(reason: str) -> str:
    return reason if reason in _END_REASONS else "provider_closed"


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
    # Configured transport base URL — the same gateway chat and transcription use.
    # None means the provider SDK's own endpoint.
    api_base: str | None
    turn_workflow_id: str | None
    final_workflow_id: str | None
    # From the voice catalog. A conversation is billed by wall-clock rather than by
    # tokens: it is the one number both providers agree on the meaning of.
    cost_per_minute: float


class VoiceSessionService:
    def __init__(
        self,
        voice_agents: VoiceAgentRepository,
        projects: ProjectRepository,
        organizations: OrganizationRepository,
        knowledge_bases: KnowledgeBaseService,
        credentials: CredentialsService,
        sessions: VoiceSessionRepository,
    ) -> None:
        self._voice_agents = voice_agents
        self._projects = projects
        self._organizations = organizations
        self._knowledge_bases = knowledge_bases
        self._credentials = credentials
        self._sessions = sessions

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

        catalog_entry = find_voice_model(config.voice.provider, config.voice.model)

        return VoiceSessionSetup(
            instructions=self._build_instructions(config, knowledge),
            voice=config.voice.voice_id or "",
            language=config.language,
            params=config.params,
            provider=config.voice.provider,
            model=config.voice.model,
            api_key=api_key,
            api_base=resolve_api_base(config.voice.provider),
            turn_workflow_id=config.turn_workflow_id,
            final_workflow_id=config.final_workflow_id,
            cost_per_minute=(catalog_entry.cost_per_minute or 0.0) if catalog_entry else 0.0,
        )

    async def open_session(
        self, *, voice_agent_id: UUID, project_id: UUID, is_debug: bool = True
    ) -> UUID:
        """Create the call's row before any audio flows.

        It exists first because the analysis hooks stamp their executions with its
        id — a hook fired mid-call has nothing to point at otherwise.
        """
        session = await self._sessions.create(
            voice_agent_id=voice_agent_id,
            project_id=project_id,
            status="active",
            is_debug=is_debug,
        )
        return session.id

    async def close_session(
        self,
        *,
        voice_session_id: UUID,
        transcript: list[dict],
        duration_sec: float,
        end_reason: str,
        input_tokens: int,
        output_tokens: int,
        cost_per_minute: float,
    ) -> None:
        """Write everything the call produced, in one go."""
        session = await self._sessions.get_by_id(voice_session_id)
        if session is None:
            return

        reason = normalize_end_reason(end_reason)
        if reason != end_reason:
            # The raw text is a provider's close frame — useful to read once, not to
            # store in a status column that code branches on.
            logger.info(
                "voice.session.closed_by_provider",
                voice_session_id=str(voice_session_id),
                detail=end_reason,
            )

        credits = compute_session_credits(duration_sec, cost_per_minute)
        await self._sessions.update(
            session,
            status="failed" if reason == "error" else "completed",
            ended_at=datetime.now(UTC),
            duration_sec=duration_sec,
            transcript=transcript,
            total_credits=credits,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            end_reason=reason,
        )

        agent = await self._voice_agents.get_by_id(session.voice_agent_id)
        if agent is not None:
            await self._voice_agents.update(
                agent,
                session_count=agent.session_count + 1,
                total_credits=agent.total_credits + credits,
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


def compute_session_credits(duration_sec: float, cost_per_minute: float) -> Decimal:
    """A conversation is billed by wall-clock, quantized to what the column holds."""
    minutes = Decimal(str(duration_sec)) / Decimal(60)
    return (minutes * Decimal(str(cost_per_minute))).quantize(
        _CREDITS_QUANTUM, rounding=ROUND_HALF_UP
    )


@asynccontextmanager
async def _voice_session_service() -> AsyncIterator[VoiceSessionService]:
    """Composition root for the non-request path: open a DB session, act, release."""
    from assemblix_api.database import get_async_session

    async for session in get_async_session():
        yield _build_service(session)
        await session.commit()
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No database session available",
    )


def _build_service(session: AsyncSession) -> VoiceSessionService:
    return VoiceSessionService(
        VoiceAgentRepository(session),
        ProjectRepository(session),
        OrganizationRepository(session),
        KnowledgeBaseService(
            KnowledgeBaseRepository(session), KnowledgeDocumentRepository(session)
        ),
        CredentialsService(CredentialsRepository(session), OrganizationUserRepository(session)),
        VoiceSessionRepository(session),
    )


async def load_voice_session_setup(*, voice_agent_id: UUID, project_id: UUID) -> VoiceSessionSetup:
    async with _voice_session_service() as service:
        return await service.build_setup(voice_agent_id=voice_agent_id, project_id=project_id)


async def open_voice_session(
    *, voice_agent_id: UUID, project_id: UUID, is_debug: bool = True
) -> UUID:
    async with _voice_session_service() as service:
        return await service.open_session(
            voice_agent_id=voice_agent_id, project_id=project_id, is_debug=is_debug
        )


async def close_voice_session(**kwargs) -> None:
    async with _voice_session_service() as service:
        await service.close_session(**kwargs)
