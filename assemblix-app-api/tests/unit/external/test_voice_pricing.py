from decimal import Decimal

import pytest

from assemblix_api.external.voice.pricing import compute_tts_cost


def test_compute_tts_cost_multiplies_chars_by_price() -> None:
    """cost = chars * cost_per_char for a known model."""
    # Arrange / Act
    cost = compute_tts_cost("elevenlabs", "eleven_multilingual_v2", 100)
    # Assert — 100 * 0.00003
    assert cost == Decimal("0.00300000")


def test_compute_tts_cost_unknown_model_raises() -> None:
    """An unregistered model raises ValueError."""
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        compute_tts_cost("elevenlabs", "nope", 10)
