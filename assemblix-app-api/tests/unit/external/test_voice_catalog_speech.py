"""Unit tests for the ElevenLabs speech models in the voice catalog."""

from __future__ import annotations

from assemblix_api.external.voice.voice_catalog import (
    find_voice_model,
    list_voice_models,
    list_voice_providers,
)


def test_elevenlabs_exposes_speech_models() -> None:
    """The elevenlabs provider is listed for the speech capability with priced models."""
    # Arrange / Act
    providers = list_voice_providers("speech")
    models = list_voice_models("elevenlabs", "speech")
    meta = find_voice_model("elevenlabs", "eleven_multilingual_v2")
    # Assert
    assert "elevenlabs" in providers
    assert any(m.id == "eleven_multilingual_v2" for m in models)
    assert meta is not None and meta.cost_per_char and meta.cost_per_char > 0
