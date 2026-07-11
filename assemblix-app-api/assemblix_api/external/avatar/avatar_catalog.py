"""Data-driven avatar-model catalog (mirror of external/voice/voice_catalog.py).

Models are declared as data in models/<provider>.json. Adding a model to an
existing provider is a JSON edit; adding a provider also needs an
AVATAR_PROVIDER_LABELS entry.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from assemblix_api.external.avatar.base import AvatarModelMetadata

_AVATAR_MODELS_DIR = Path(__file__).parent / "models"

# Registered avatar providers -> display label. A provider without an entry here
# is invisible even if a JSON exists.
AVATAR_PROVIDER_LABELS: dict[str, str] = {"anam": "Anam"}


@cache
def _provider_models(provider: str) -> tuple[AvatarModelMetadata, ...]:
    path = _AVATAR_MODELS_DIR / f"{provider}.json"
    if not path.exists():
        return ()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return tuple(AvatarModelMetadata.model_validate(entry) for entry in data["models"])


def find_avatar_model(provider: str, model: str) -> AvatarModelMetadata | None:
    if provider not in AVATAR_PROVIDER_LABELS:
        return None
    return next((m for m in _provider_models(provider) if m.id == model), None)


def list_avatar_models(provider: str) -> list[AvatarModelMetadata]:
    if provider not in AVATAR_PROVIDER_LABELS:
        return []
    return list(_provider_models(provider))


def list_avatar_providers() -> list[str]:
    return [p for p in AVATAR_PROVIDER_LABELS if list_avatar_models(p)]
