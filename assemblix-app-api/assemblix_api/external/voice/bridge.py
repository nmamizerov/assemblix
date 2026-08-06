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
    pass


@dataclass(frozen=True)
class BridgeError:
    code: str | None
    message: str


BridgeEvent = AudioDelta | UserTranscript | AgentTranscript | SpeechStarted | TurnEnded | BridgeError


class RealtimeBridge(Protocol):
    async def connect(
        self,
        *,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
    ) -> None: ...

    async def send_audio(self, pcm: bytes) -> None: ...

    async def interrupt(self) -> None: ...

    def events(self) -> AsyncIterator[BridgeEvent]: ...

    async def close(self) -> None: ...
