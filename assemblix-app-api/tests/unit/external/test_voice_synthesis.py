import pytest

from assemblix_api.external.voice.synthesis import SynthesisResult, synthesize


async def _fake_eleven(*, api_key, voice_id, model, text):
    return b"AUDIO"


async def test_synthesize_routes_to_elevenlabs(mocker) -> None:
    """A speech-capability elevenlabs model routes to the ElevenLabs client."""
    # Arrange
    mocker.patch(
        "assemblix_api.external.voice.synthesis.elevenlabs.synthesize",
        side_effect=_fake_eleven,
    )
    # Act
    result = await synthesize(
        text="hello",
        provider="elevenlabs",
        model="eleven_multilingual_v2",
        voice_id="v1",
        api_key="xi-key",
    )
    # Assert
    assert isinstance(result, SynthesisResult)
    assert result.audio_bytes == b"AUDIO"
    assert result.chars == 5


async def test_synthesize_unknown_model_raises() -> None:
    """An unregistered model raises ValueError before any network call."""
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        await synthesize(
            text="x", provider="elevenlabs", model="nope", voice_id="v1", api_key="xi-key"
        )
