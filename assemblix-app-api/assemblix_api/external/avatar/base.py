"""Metadata contract for the avatar-model registry (mirrors external/voice/base.py)."""

from __future__ import annotations

from assemblix_api.dto.base import DTOModel


class AvatarModelMetadata(DTOModel):
    """Static metadata for one avatar model, loaded from a provider JSON file."""

    id: str
    label: str
    description: str | None = None
    # Provider-native avatar model identifier passed back in personaConfig.avatarModel.
    avatar_model: str
    cost_per_minute: float | None = None
