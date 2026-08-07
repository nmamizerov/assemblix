"""Voice session endpoints: mint a short-lived token, then stream audio over it.

The WebSocket handler is the one place in the app that is not request/response,
but it stays a transport: it authorizes the token, hands assembly to
``VoiceSessionService`` and plumbing to ``VoiceSessionRuntime``, and owns nothing
of its own beyond adapting the socket.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.core.settings import get_settings
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
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.voice_agent_service import VoiceAgentService
from assemblix_api.services.voice_session_service import load_voice_session_setup

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
        setup = await load_voice_session_setup(voice_agent_id=voice_agent_id, project_id=project_id)
    except HTTPException as exc:
        await websocket.send_json({"type": "session.closed", "reason": exc.detail})
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
