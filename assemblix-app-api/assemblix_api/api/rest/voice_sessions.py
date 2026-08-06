"""Voice session endpoints: mint a short-lived token, then stream audio over it.

The WebSocket handler is the one place in the app that is not request/response.
It holds a DB connection only while assembling the session (agent config,
knowledge, provider key) and releases it before any audio flows — a call lasts
minutes and must not occupy a pooled connection for that long.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.core.settings import get_settings
from assemblix_api.database import get_async_session
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
from assemblix_api.dependencies import (
    get_auth_context,
    get_project_service,
    get_voice_agent_service,
)
from assemblix_api.dto.responses.voice_session import VoiceSessionTokenResponse
from assemblix_api.external.voice.bridge_dispatch import create_bridge
from assemblix_api.realtime.runtime import VoiceSessionRuntime
from assemblix_api.realtime.session_token import (
    InvalidSessionToken,
    mint_session_token,
    verify_session_token,
)
from assemblix_api.schemas.voice_agent import VoiceAgentConfig
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.voice_agent_service import VoiceAgentService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/voice-agents", tags=["Voice Agents"])

_TOKEN_TTL_SECONDS = 60


@router.post("/{agent_id}/sessions", response_model=VoiceSessionTokenResponse)
async def create_voice_session(
    agent_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
) -> VoiceSessionTokenResponse:
    """Authorize the caller and hand back a token good for one session."""
    agent = await service.get_voice_agent(agent_id)
    await project_service.authorize_project_access(auth, agent.project_id)

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This voice agent is not active",
        )

    return VoiceSessionTokenResponse(
        token=mint_session_token(
            voice_agent_id=agent.id,
            project_id=agent.project_id,
            ttl_seconds=_TOKEN_TTL_SECONDS,
        ),
        expires_in=_TOKEN_TTL_SECONDS,
    )


@dataclass
class _SessionSetup:
    """Everything a call needs, read once so the session itself touches no DB."""

    instructions: str
    voice: str
    language: str
    params: dict
    provider: str
    model: str
    api_key: str


async def _load_setup(voice_agent_id: UUID, project_id: UUID) -> _SessionSetup:
    """Assemble the session while briefly holding a DB connection."""
    async for session in get_async_session():
        agent = await VoiceAgentRepository(session).get_by_id(voice_agent_id)
        if agent is None or agent.project_id != project_id:
            raise InvalidSessionToken("Voice agent not found for this token")

        config = VoiceAgentConfig(**agent.config)

        project = await ProjectRepository(session).get_by_id(project_id)
        if project is None:
            raise InvalidSessionToken("Project not found")
        organization = await OrganizationRepository(session).get_by_id(project.organization_id)
        if organization is None:
            raise InvalidSessionToken("Organization not found")

        knowledge = ""
        if config.knowledge_base_ids:
            kb_service = KnowledgeBaseService(
                KnowledgeBaseRepository(session), KnowledgeDocumentRepository(session)
            )
            knowledge = await kb_service.get_combined_content(
                [UUID(kb_id) for kb_id in config.knowledge_base_ids]
            )

        credentials_service = CredentialsService(
            CredentialsRepository(session), OrganizationUserRepository(session)
        )
        api_key, _ = await credentials_service.get_voice_api_key_with_fallback(
            credentials_id=UUID(config.voice.credential_id) if config.voice.credential_id else None,
            project_id=project_id,
            voice_provider=config.voice.provider,
            organization_plan=organization.plan,
        )

        return _SessionSetup(
            instructions=_build_instructions(config, knowledge),
            voice=config.voice.voice_id or "",
            language=config.language,
            params=config.params,
            provider=config.voice.provider,
            model=config.voice.model,
            api_key=api_key,
        )

    raise InvalidSessionToken("No database session available")


def _build_instructions(config: VoiceAgentConfig, knowledge: str) -> str:
    """Knowledge bases are inlined once, at session start — no retrieval at call time."""
    parts = [instruction.content for instruction in config.instructions]
    if knowledge:
        parts.append(f"---\nБаза знаний:\n{knowledge}\n---")
    if config.first_message:
        parts.append(f"Начни разговор с фразы: {config.first_message}")
    return "\n\n".join(parts)


class _WebSocketChannel:
    """Adapts a Starlette WebSocket to the runtime's narrow client contract."""

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket

    async def send_json(self, data: dict) -> None:
        await self._ws.send_json(data)

    async def send_bytes(self, data: bytes) -> None:
        await self._ws.send_bytes(data)

    async def __aiter__(self) -> AsyncIterator[bytes | dict]:
        while True:
            message = await self._ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            if (payload := message.get("bytes")) is not None:
                yield payload
            elif (text := message.get("text")) is not None:
                yield json.loads(text)


@router.websocket("/sessions/{token}/stream")
async def stream_voice_session(websocket: WebSocket, token: str) -> None:
    try:
        voice_agent_id, project_id = verify_session_token(token)
    except InvalidSessionToken:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        setup = await _load_setup(voice_agent_id, project_id)
    except InvalidSessionToken as exc:
        await websocket.send_json({"type": "session.closed", "reason": str(exc)})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception:
        logger.exception("voice_session_setup_failed", voice_agent_id=str(voice_agent_id))
        await websocket.send_json({"type": "session.closed", "reason": "setup_failed"})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    runtime = VoiceSessionRuntime(
        bridge=create_bridge(provider=setup.provider, api_key=setup.api_key, model=setup.model),
        client=_WebSocketChannel(websocket),
        instructions=setup.instructions,
        voice=setup.voice,
        language=setup.language,
        params=setup.params,
        max_session_sec=get_settings().voice_session_max_seconds,
    )
    try:
        await runtime.run()
    except WebSocketDisconnect:
        logger.info("voice_session_client_gone", voice_agent_id=str(voice_agent_id))
    except Exception:
        logger.exception("voice_session_failed", voice_agent_id=str(voice_agent_id))
    finally:
        with contextlib.suppress(RuntimeError):
            await websocket.close()
