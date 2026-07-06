"""Metadata contracts for the voice-model registry.

Mirrors ``external/llm/base.py`` but for speech models. ``capability`` groups
models by feature — only ``transcription`` ships today; ``speech``/``realtime``
reserve the shape for future TTS / streaming without a schema change. ``route``
tells the transcription service how to call the model.
"""

from __future__ import annotations

from typing import Literal

from assemblix_api.dto.base import DTOModel


class VoiceModelMetadata(DTOModel):
    """Static metadata for a single voice model, loaded from a provider JSON file."""

    id: str
    label: str
    description: str | None = None
    capability: Literal["transcription", "speech", "realtime"]
    route: Literal["transcription", "completion"]
    cost_per_minute: float | None = None
