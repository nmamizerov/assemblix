"""Provider seam for speech-to-speech (conversation) sessions.

Sibling of ``realtime_dispatch.py``, which does the same for streaming TTS. The
difference is direction: TTS is text-in/audio-out, a conversation bridge is
audio-in/audio-and-events-out. Provider vocabulary stops at this boundary — the
runtime above it never learns which provider is connected.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AudioDelta:
    """A chunk of agent speech, PCM16 mono little-endian at the session's rate."""

    pcm: bytes


@dataclass(frozen=True)
class UserTranscript:
    text: str
    is_final: bool


@dataclass(frozen=True)
class AgentTranscript:
    text: str
    is_final: bool


@dataclass(frozen=True)
class SpeechStarted:
    """The user began speaking. The runtime must flush client-side playback."""


@dataclass(frozen=True)
class TurnEnded:
    """A response finished. Token counts are ``None`` when the provider omits usage."""

    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class BridgeError:
    code: str | None
    message: str
    is_fatal: bool


@dataclass(frozen=True)
class SessionClosed:
    """Terminal event: the provider connection ended. Always the last event seen."""

    reason: str


BridgeEvent = (
    AudioDelta
    | UserTranscript
    | AgentTranscript
    | SpeechStarted
    | TurnEnded
    | BridgeError
    | SessionClosed
)


class RealtimeBridge(Protocol):
    # Providers do not agree on rates: OpenAI is 24kHz both ways, Gemini Live wants
    # 16kHz in and answers at 24kHz. The browser reaches either natively via
    # `new AudioContext({ sampleRate })`, so the rate travels to it instead of being
    # resampled anywhere.
    input_sample_rate: int
    output_sample_rate: int

    async def connect(
        self,
        *,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
    ) -> None: ...

    async def send_audio(self, pcm: bytes) -> None: ...

    async def interrupt(self, *, audio_end_ms: int) -> None:
        """Cut off in-flight agent speech.

        ``audio_end_ms`` is how much of the current agent turn's audio the user
        actually heard — the bridge has no playback queue, so the runtime owns
        that number and must supply it.
        """
        ...

    def events(self) -> AsyncIterator[BridgeEvent]: ...

    async def close(self) -> None: ...
