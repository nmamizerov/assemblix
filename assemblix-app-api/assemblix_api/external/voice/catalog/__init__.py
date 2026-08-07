"""The voice-model registry: which providers and models exist, for which
capability, at what price.

``models/*.json`` is the data, ``metadata.py`` is the type it is validated
against, ``registry.py`` reads it. Adding a model is a JSON edit.
"""

from assemblix_api.external.voice.catalog.metadata import VoiceModelMetadata
from assemblix_api.external.voice.catalog.registry import (
    VOICE_PROVIDER_LABELS,
    find_voice_model,
    has_conversation_route,
    has_realtime_route,
    list_voice_models,
    list_voice_providers,
)

__all__ = [
    "VOICE_PROVIDER_LABELS",
    "VoiceModelMetadata",
    "find_voice_model",
    "has_conversation_route",
    "has_realtime_route",
    "list_voice_models",
    "list_voice_providers",
]
