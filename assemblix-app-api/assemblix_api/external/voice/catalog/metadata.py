"""Metadata contracts for the voice-model registry.

Mirrors ``external/llm/base.py`` but for speech models. ``capability`` groups
models by feature — ``transcription`` and ``speech`` ship today; ``realtime``
reserves the shape for future streaming without a schema change. ``route``
tells the calling service how to invoke the model.

``conversation`` is speech-to-speech (a duplex session where the provider both
listens and speaks). It is distinct from ``realtime``, which in this codebase
means streaming TTS only — do not overload one for the other.
"""

from __future__ import annotations

from typing import Literal

from assemblix_api.dto.base import DTOModel


class VoiceModelMetadata(DTOModel):
    """Static metadata for a single voice model, loaded from a provider JSON file."""

    id: str
    label: str
    description: str | None = None
    capability: Literal["transcription", "speech", "realtime", "conversation"]
    route: Literal["transcription", "completion", "speech", "realtime", "conversation"]
    cost_per_minute: float | None = None
    cost_per_char: float | None = None
