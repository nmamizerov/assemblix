"""Voice-model registry — the data-driven catalog of speech models.

Mirror of ``external/llm/model_catalog`` + ``models_loader``: models are declared
as data in ``models/<provider>.json`` and loaded/validated here. ``transcription``
and ``speech`` models ship today; adding a model to an existing provider is a JSON
edit, adding a provider also needs a ``VOICE_PROVIDER_LABELS`` entry.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from assemblix_api.external.voice.base import VoiceModelMetadata

_VOICE_MODELS_DIR = Path(__file__).parent / "models"

# Registered voice providers → display label. This is the gate for what the API
# exposes; a provider without an entry here is invisible even if a JSON exists.
VOICE_PROVIDER_LABELS: dict[str, str] = {"openai": "OpenAI", "elevenlabs": "ElevenLabs"}


@cache
def _provider_models(provider: str) -> tuple[VoiceModelMetadata, ...]:
    path = _VOICE_MODELS_DIR / f"{provider}.json"
    if not path.exists():
        return ()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return tuple(VoiceModelMetadata.model_validate(entry) for entry in data["models"])


def find_voice_model(provider: str, model: str) -> VoiceModelMetadata | None:
    """Return the registry entry for ``(provider, model)`` or ``None``."""
    if provider not in VOICE_PROVIDER_LABELS:
        return None
    return next((m for m in _provider_models(provider) if m.id == model), None)


def list_voice_models(provider: str, capability: str = "transcription") -> list[VoiceModelMetadata]:
    """Models of a provider filtered by ``capability`` (empty if unregistered)."""
    if provider not in VOICE_PROVIDER_LABELS:
        return []
    return [m for m in _provider_models(provider) if m.capability == capability]


def list_voice_providers(capability: str = "transcription") -> list[str]:
    """Providers that expose at least one model with the given ``capability``."""
    return [p for p in VOICE_PROVIDER_LABELS if list_voice_models(p, capability)]


def has_realtime_route(provider: str, model: str) -> bool:
    """True when ``(provider, model)`` is registered as a realtime (WS-streaming) voice model."""
    if provider not in VOICE_PROVIDER_LABELS:
        return False
    return any(m.id == model and m.capability == "realtime" for m in _provider_models(provider))
