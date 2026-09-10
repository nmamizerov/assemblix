"""One resolved text-to-speech target, shared by both callers of the TTS seam.

Voice-in-workflows (the agent node) and Voice Agents (half-cascade output) both
need the same three moves: turn a ``VoiceOutputConfig`` into a usable key, open a
streaming session with it, and price what it synthesized. Neither the node's
config types nor the voice agent's cross this boundary — only the resolved value
does.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from assemblix_api.external.voice.pricing import compute_tts_cost
from assemblix_api.external.voice.streaming_tts import (
    OnError,
    RealtimeSession,
    create_realtime_session,
)
from assemblix_api.external.voice.streaming_tts import (
    output_sample_rate as streaming_output_sample_rate,
)
from assemblix_api.external.voice.streaming_tts.elevenlabs import OnAudio
from assemblix_api.schemas.node import VoiceOutputConfig


class KeyResolver(Protocol):
    """The one method this module needs from CredentialsService."""

    async def get_voice_api_key_with_fallback(
        self, credentials_id: UUID | None, project_id: UUID, voice_provider: str
    ) -> tuple[str, bool]: ...


class SpeechOutput:
    """A resolved synthesis target: config plus key, ready to open a session."""

    __slots__ = ("api_key", "model", "provider", "uses_system_key", "voice_id")

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        voice_id: str,
        api_key: str,
        uses_system_key: bool,
    ) -> None:
        self.provider = provider
        self.model = model
        self.voice_id = voice_id
        self.api_key = api_key
        self.uses_system_key = uses_system_key


async def resolve(
    voice: VoiceOutputConfig, *, project_id: UUID, credentials: KeyResolver
) -> SpeechOutput:
    """Resolve a voice config into a synthesis target.

    Raises:
        ValueError: the config names no voice — there is nothing to speak with.
    """
    if not voice.voice_id:
        raise ValueError(f"Voice provider {voice.provider!r} was configured without a voice")
    api_key, uses_system_key = await credentials.get_voice_api_key_with_fallback(
        credentials_id=UUID(voice.credential_id) if voice.credential_id else None,
        project_id=project_id,
        voice_provider=voice.provider,
    )
    return SpeechOutput(
        provider=voice.provider,
        model=voice.model,
        voice_id=voice.voice_id,
        api_key=api_key,
        uses_system_key=uses_system_key,
    )


def open_stream(
    out: SpeechOutput, *, on_audio: OnAudio, on_error: OnError | None = None
) -> RealtimeSession:
    """Build (not yet open) the streaming session for this target."""
    return create_realtime_session(
        provider=out.provider,
        api_key=out.api_key,
        voice_id=out.voice_id,
        model=out.model,
        on_audio=on_audio,
        on_error=on_error,
    )


def output_sample_rate(out: SpeechOutput) -> int:
    """The rate this target's audio will arrive at, known before it is opened."""
    return streaming_output_sample_rate(out.provider)


def cost_usd(out: SpeechOutput, chars: int) -> Decimal:
    """USD the provider charges for synthesizing ``chars`` with this target."""
    return compute_tts_cost(out.provider, out.model, chars)
