"""Metadata contract for the avatar-model registry (mirrors external/voice/base.py)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from assemblix_api.dto.base import DTOModel


class AvatarModelMetadata(DTOModel):
    """Static metadata for one avatar model, loaded from a provider JSON file."""

    id: str
    label: str
    description: str | None = None
    # Provider-native avatar model identifier passed back in personaConfig.avatarModel.
    avatar_model: str
    cost_per_minute: float | None = None


class AvatarOutput(Protocol):
    """Where the agent's voice goes during an avatar call."""

    async def push(self, pcm: bytes, sample_rate: int) -> None: ...

    async def end_utterance(self) -> None: ...

    async def interrupt(self) -> int | None: ...


@dataclass
class VendorSession:
    """A started vendor avatar. Without ``output`` the avatar is fed over LiveKit's
    data-stream protocol; without ``stop`` deleting the room ends it."""

    session_id: str
    output: AvatarOutput | None = None
    stop: Callable[[], Awaitable[None]] | None = None
