"""Streaming speech-to-text seam for cascade voice agents."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SttResult:
    text: str
    is_final: bool


class SttUnavailable(Exception):
    """The provider could not be reached after repeated attempts."""


class SttStream(Protocol):
    async def open(self, *, language: str) -> None: ...

    async def send_audio(self, pcm: bytes) -> None:
        """PCM16 mono 16 kHz."""
        ...

    async def finalize(self) -> None:
        """Ask for the current phrase to be finalised now."""
        ...

    def results(self) -> AsyncIterator[SttResult]: ...

    async def close(self) -> None: ...

    @property
    def billed_seconds(self) -> float: ...
