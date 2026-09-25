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
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.core.settings import get_settings
from assemblix_api.dependencies import (
    get_auth_context,
    get_project_service,
    get_voice_agent_service,
    get_voice_session_history_service,
)
from assemblix_api.dto.base import PaginatedResponse
from assemblix_api.dto.requests.voice_agent import VoiceSessionCreateRequest
from assemblix_api.dto.responses.voice_session import (
    VoiceSessionDetailResponse,
    VoiceSessionMedia,
    VoiceSessionResponse,
    VoiceSessionTokenResponse,
)
from assemblix_api.external.avatar.errors import AvatarError
from assemblix_api.external.voice import speech_out
from assemblix_api.external.voice.conversation import create_bridge
from assemblix_api.realtime.hooks import TurnDispatcher
from assemblix_api.realtime.livekit.channel import LiveKitChannel
from assemblix_api.realtime.livekit.tokens import USER_IDENTITY, new_room_name, participant_token
from assemblix_api.realtime.runtime import VoiceSessionRuntime
from assemblix_api.realtime.session_token import (
    InvalidSessionToken,
    mint_session_token,
    verify_session_token,
)
from assemblix_api.schemas.voice_agent import VoiceAgentConfig
from assemblix_api.services.avatar_service import ResolvedAvatar
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.voice_agent_service import VoiceAgentService
from assemblix_api.services.voice_session_history_service import VoiceSessionHistoryService
from assemblix_api.services.voice_session_service import (
    close_voice_session,
    load_voice_session_setup,
    open_voice_session,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/voice-agents", tags=["Voice Agents"])
# Sessions are addressable on their own — a call outlives the page it was made from.
sessions_router = APIRouter(prefix="/voice-sessions", tags=["Voice Agents"])

_TOKEN_TTL_SECONDS = 60


@router.get("/{agent_id}/sessions", response_model=PaginatedResponse[VoiceSessionResponse])
async def list_voice_sessions(
    agent_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
    history: VoiceSessionHistoryService = Depends(get_voice_session_history_service),
) -> PaginatedResponse[VoiceSessionResponse]:
    agent = await service.get_voice_agent(agent_id)
    await project_service.authorize_project_access(auth, agent.project_id)

    items, total = await history.list_for_agent(agent_id, limit=limit, offset=(page - 1) * limit)
    return PaginatedResponse(data=items, total=total, page=page, limit=limit)


@sessions_router.get("/{voice_session_id}", response_model=VoiceSessionDetailResponse)
async def get_voice_session(
    voice_session_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    project_service: ProjectService = Depends(get_project_service),
    history: VoiceSessionHistoryService = Depends(get_voice_session_history_service),
) -> VoiceSessionDetailResponse:
    detail, project_id = await history.get_detail(voice_session_id)
    await project_service.authorize_project_access(auth, project_id)
    return detail


@router.post("/{agent_id}/sessions", response_model=VoiceSessionTokenResponse)
async def create_voice_session(
    agent_id: UUID,
    request: VoiceSessionCreateRequest | None = None,
    auth: AuthContext = Depends(get_auth_context),
    service: VoiceAgentService = Depends(get_voice_agent_service),
    project_service: ProjectService = Depends(get_project_service),
) -> VoiceSessionTokenResponse:
    """Authorize the caller and hand back a token good for one session.

    An optional ``clientId`` in the body is sealed into the token and travels with the
    call: it lands on the ``voice_sessions`` row and on every analysis-hook run the
    call starts, so a conversation and its scoring workflows share one ClientSession.
    """
    agent = await service.get_voice_agent(agent_id)
    await project_service.authorize_project_access(auth, agent.project_id)

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This voice agent is not active",
        )

    room: str | None = None
    media: VoiceSessionMedia | None = None
    if VoiceAgentConfig(**agent.config).avatar is not None:
        settings = get_settings()
        if not settings.livekit_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Avatars need LiveKit: set LIVEKIT_* (see self-hosting docs)",
            )
        room = new_room_name()
        media = VoiceSessionMedia(
            transport="livekit",
            url=settings.livekit_public_url,
            token=participant_token(room, USER_IDENTITY, ttl_seconds=_TOKEN_TTL_SECONDS),
        )

    return VoiceSessionTokenResponse(
        token=mint_session_token(
            voice_agent_id=agent.id,
            project_id=agent.project_id,
            # A project API key means a program is placing this call from someone's
            # product; a JWT means a person is rehearsing in the editor.
            is_debug=auth.scoped_project_id is None,
            client_id=request.client_id if request else None,
            ttl_seconds=_TOKEN_TTL_SECONDS,
            room=room,
        ),
        expires_in=_TOKEN_TTL_SECONDS,
        media=media,
    )


def avatar_call_mismatch(room: str | None, avatar: ResolvedAvatar | None) -> str | None:
    """A token minted for an avatar call whose agent lost its avatar cannot run:
    the caller already joined the media room and waits for a face."""
    if room is not None and avatar is None:
        return "avatar_unavailable"
    return None


class _WebSocketChannel:
    """Adapts a Starlette WebSocket to the runtime's narrow client contract."""

    media = "ws"

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket

    async def send_json(self, data: dict) -> None:
        await self._ws.send_json(data)

    async def send_bytes(self, data: bytes) -> None:
        await self._ws.send_bytes(data)

    async def interrupt_playback(self) -> int | None:
        # The browser owns playback and flushes on `speech.started`.
        return None

    async def end_of_utterance(self) -> None:
        return None

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
        scope = verify_session_token(token)
    except InvalidSessionToken:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        setup = await load_voice_session_setup(
            voice_agent_id=scope.voice_agent_id, project_id=scope.project_id
        )
    except HTTPException as exc:
        await websocket.send_json({"type": "session.closed", "reason": exc.detail})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception:
        logger.exception("voice_session_setup_failed", voice_agent_id=str(scope.voice_agent_id))
        await websocket.send_json({"type": "session.closed", "reason": "setup_failed"})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    try:
        voice_session_id = await open_voice_session(
            voice_agent_id=scope.voice_agent_id,
            project_id=scope.project_id,
            is_debug=scope.is_debug,
            client_id=scope.client_id,
        )
    except HTTPException as exc:
        # Notably the plan's concurrent-call ceiling: the browser gets a reason
        # rather than a socket that dies without one.
        await websocket.send_json({"type": "session.closed", "reason": exc.detail})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    mismatch = avatar_call_mismatch(scope.room, setup.avatar)
    avatar_call = scope.room is not None and setup.avatar is not None
    bridge = create_bridge(
        provider=setup.provider,
        api_key=setup.api_key,
        model=setup.model,
        api_base=setup.api_base,
        speech_out=setup.tts,
    )
    ws_channel = _WebSocketChannel(websocket)
    client: Any = LiveKitChannel(ws_channel) if avatar_call else ws_channel
    media: Any = None

    async def prepare_avatar() -> None:
        nonlocal media
        from assemblix_api.realtime.livekit.session import open_avatar_media

        assert scope.room is not None and setup.avatar is not None
        media = await open_avatar_media(
            room_name=scope.room,
            avatar=setup.avatar,
            timeout=get_settings().avatar_join_timeout_seconds,
        )
        client.attach(
            mic=media.mic(bridge.input_sample_rate),
            output=media.output,
            output_sample_rate=bridge.output_sample_rate,
        )

    async def close_media() -> None:
        nonlocal media
        if media is not None:
            opened, media = media, None
            await opened.close()

    runtime = VoiceSessionRuntime(
        bridge=bridge,
        client=client,
        instructions=setup.instructions,
        voice=setup.voice,
        language=setup.language,
        params=setup.params,
        max_session_sec=get_settings().voice_session_max_seconds,
        dispatcher=TurnDispatcher(
            voice_session_id=voice_session_id,
            turn_workflow_id=setup.turn_workflow_id,
            final_workflow_id=setup.final_workflow_id,
            client_id=scope.client_id,
        ),
        prepare=prepare_avatar if avatar_call else None,
        on_stopped=close_media if avatar_call else None,
    )

    end_reason = "error"
    close_reason: str | None = mismatch
    try:
        if mismatch is None:
            end_reason = await runtime.run()
    except AvatarError as exc:
        close_reason = exc.reason
        logger.warning(
            "voice_session_avatar_failed",
            voice_agent_id=str(scope.voice_agent_id),
            reason=exc.reason,
            error=str(exc),
        )
        with contextlib.suppress(Exception):
            await bridge.close()
    except WebSocketDisconnect:
        end_reason = "user_hangup"
        logger.info("voice_session_client_gone", voice_agent_id=str(scope.voice_agent_id))
    except Exception:
        logger.exception("voice_session_failed", voice_agent_id=str(scope.voice_agent_id))
    finally:
        await close_media()
        input_tokens, output_tokens = runtime.usage
        tts_cost_usd = (
            speech_out.cost_usd(setup.tts, runtime.speech_chars)
            if setup.tts is not None
            else Decimal(0)
        )
        await close_voice_session(
            voice_session_id=voice_session_id,
            transcript=runtime.transcript,
            duration_sec=runtime.duration_sec,
            end_reason=end_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_per_minute=setup.cost_per_minute,
            uses_system_key=setup.uses_system_key,
            tts_cost_usd=tts_cost_usd,
            tts_uses_system_key=setup.tts.uses_system_key if setup.tts else False,
        )
        if close_reason is not None:
            with contextlib.suppress(Exception):
                await websocket.send_json({"type": "session.closed", "reason": close_reason})
            with contextlib.suppress(RuntimeError):
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        with contextlib.suppress(RuntimeError):
            await websocket.close()
