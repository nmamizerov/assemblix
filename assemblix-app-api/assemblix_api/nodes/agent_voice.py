"""Voice orchestration for the agent node — kept out of agent_node.execute to stay lean.

Two mutually exclusive paths per run: a live realtime WS session (streaming) or one buffered
base64 synthesis (non-streaming). END has no synthesis, so this is the only place TTS happens
— a double call is structurally impossible.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from uuid import UUID

from assemblix_api.core.settings import get_settings
from assemblix_api.external.voice.pricing import compute_tts_cost
from assemblix_api.external.voice.realtime import RealtimeTTSSession
from assemblix_api.external.voice.synthesis import synthesize
from assemblix_api.external.voice.voice_catalog import has_realtime_route
from assemblix_api.schemas.execution import ExecutionContext
from assemblix_api.schemas.node import AgentNodeConfig

OnDelta = Callable[[str], Awaitable[None]]
OnAudio = Callable[..., Awaitable[None]]


def _voice_ready(cfg: AgentNodeConfig) -> bool:
    v = cfg.voice
    return bool(cfg.output_type == "voice" and v and v.voice_id and v.model and v.provider)


def should_stream_voice(
    cfg: AgentNodeConfig, *, on_delta: OnDelta | None, on_audio: OnAudio | None
) -> bool:
    """Live-audio gate: voice-ready, realtime model, and both sinks present (which already
    encode request.stream x node.stream x text-format from the caller)."""
    if not _voice_ready(cfg) or on_delta is None or on_audio is None:
        return False
    assert cfg.voice is not None
    return has_realtime_route(cfg.voice.provider, cfg.voice.model)


async def _resolve_key(cfg: AgentNodeConfig, context: ExecutionContext) -> tuple[str, bool]:
    assert context.credential_service is not None
    assert context.organization_plan is not None
    v = cfg.voice
    assert v is not None
    return await context.credential_service.get_voice_api_key_with_fallback(
        credentials_id=UUID(v.credential_id) if v.credential_id else None,
        project_id=context.project_id,
        voice_provider=v.provider,
        organization_plan=context.organization_plan,
    )


async def open_voice_session(
    cfg: AgentNodeConfig,
    context: ExecutionContext,
    *,
    on_delta: OnDelta,
    on_audio: OnAudio,
) -> tuple[RealtimeTTSSession, OnDelta, bool]:
    """Open a live WS session; return (session, tee_on_delta, is_system_key)."""
    assert cfg.voice is not None
    api_key, is_system_key = await _resolve_key(cfg, context)
    session = RealtimeTTSSession(
        api_key=api_key,
        voice_id=cfg.voice.voice_id,  # type: ignore[arg-type]
        model=cfg.voice.model,
        on_audio=on_audio,
    )
    await session.open()

    async def tee(text: str) -> None:
        await on_delta(text)
        await session.send_text(text)

    return session, tee, is_system_key


def voice_cost_metadata(cfg: AgentNodeConfig, *, chars: int, is_system_key: bool) -> dict:
    assert cfg.voice is not None
    cost = compute_tts_cost(cfg.voice.provider, cfg.voice.model, chars)
    return {
        "cost": float(cost),
        "cost_kind": "voice",
        "used_system_key": is_system_key,
        "chars": chars,
        "voice_provider": cfg.voice.provider,
        "voice_model": cfg.voice.model,
    }


async def synthesize_buffered(
    cfg: AgentNodeConfig, context: ExecutionContext, text: str
) -> tuple[dict | None, dict]:
    """Non-streaming path: one base64 synthesis under the char cap. Returns
    (audio_dict|None, cost_metadata). Over the cap or empty text -> (None, {})."""
    assert cfg.voice is not None
    limit = get_settings().voice_output_max_chars
    if not text or len(text) > limit or not cfg.voice.voice_id:
        return None, {}
    api_key, is_system_key = await _resolve_key(cfg, context)
    result = await synthesize(
        text=text,
        provider=cfg.voice.provider,
        model=cfg.voice.model,
        voice_id=cfg.voice.voice_id,
        api_key=api_key,
    )
    audio = {
        "base64": base64.b64encode(result.audio_bytes).decode("ascii"),
        "format": "mp3",
        "voiceId": cfg.voice.voice_id,
        "model": cfg.voice.model,
    }
    return audio, voice_cost_metadata(cfg, chars=result.chars, is_system_key=is_system_key)
