"""Realtime (streaming) TTS provider seam — sibling of ``synthesis.py``.

The realtime path was ElevenLabs-only; this factory picks the session class per
provider, keeping the agent node transport-agnostic. Each session shares the same
duck-typed contract (``RealtimeSession``): ``open() / send_text() / flush_and_close()``
plus an ``on_audio(pcm, alignment)`` callback wired at construction.

For Yandex the *model id* also selects the streaming mode (see ``_YANDEX_MODEL_MODE``),
so the existing model picker doubles as the mode switch — no extra config field.
"""

from __future__ import annotations

from typing import Protocol

from assemblix_api.external.voice.realtime import OnAudio, RealtimeTTSSession
from assemblix_api.external.voice.yandex_realtime import Mode, YandexRealtimeSession


class RealtimeSession(Protocol):
    async def open(self) -> None: ...
    async def send_text(self, text: str) -> None: ...
    async def flush_and_close(self) -> int: ...


# Yandex catalog id → streaming mode. "utterance" = sentence-buffered (best prosody);
# "stream" = bidirectional (lowest latency).
_YANDEX_MODEL_MODE: dict[str, Mode] = {
    "yandex-tts-v3": "utterance",
    "yandex-tts-v3-stream": "stream",
}


def create_realtime_session(
    *,
    provider: str,
    api_key: str,
    voice_id: str,
    model: str,
    on_audio: OnAudio,
) -> RealtimeSession:
    """Build the realtime TTS session for ``provider``.

    Raises:
        NotImplementedError: the provider has no realtime route.
    """
    if provider == "elevenlabs":
        return RealtimeTTSSession(
            api_key=api_key, voice_id=voice_id, model=model, on_audio=on_audio
        )
    if provider == "yandex":
        return YandexRealtimeSession(
            credential=api_key,
            voice_id=voice_id,
            model=model,
            on_audio=on_audio,
            mode=_YANDEX_MODEL_MODE.get(model, "utterance"),
        )
    raise NotImplementedError(f"No realtime route for provider {provider!r}")
