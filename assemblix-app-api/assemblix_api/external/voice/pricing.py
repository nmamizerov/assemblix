"""Per-character cost for text-to-speech, mirroring external/llm/pricing.py."""

from __future__ import annotations

from decimal import Decimal

from assemblix_api.external.voice.voice_catalog import find_voice_model


def compute_tts_cost(provider: str, model: str, chars: int) -> Decimal:
    """USD cost of synthesizing ``chars`` characters with ``(provider, model)``.

    Raises:
        ValueError: the pair is not in the voice registry.
    """
    meta = find_voice_model(provider, model)
    if meta is None:
        raise ValueError(f"Unknown or unsupported voice model: {provider}/{model}")
    cost_per_char = Decimal(str(meta.cost_per_char or 0))
    return cost_per_char * chars
