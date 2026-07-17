from assemblix_api.schemas.execution import AudioInput

from ._helpers import make_context


def test_context_carries_audio_input() -> None:
    # Arrange
    audio = AudioInput(bytes=b"RIFFxxxx", mime="audio/wav", filename="voice.wav")
    # Act
    context = make_context(audio_input=audio)
    # Assert
    assert context.audio_input is audio


def test_context_audio_input_defaults_none() -> None:
    # Arrange / Act
    context = make_context()
    # Assert
    assert context.audio_input is None
