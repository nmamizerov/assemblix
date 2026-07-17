import pytest

from assemblix_api.execution.voice_gate import ensure_audio_run_is_synchronous


def test_audio_run_rejected_when_queued() -> None:
    # Arrange
    input_data = {"input_type": "audio"}

    # Act / Assert — raising is the observable outcome, so Act and Assert
    # are the same `pytest.raises` block.
    with pytest.raises(ValueError, match="synchronous"):
        ensure_audio_run_is_synchronous(input_data=input_data, queued=True)


def test_text_run_allowed_when_queued() -> None:
    # Arrange
    input_data = {"input_type": "text"}

    # Act
    ensure_audio_run_is_synchronous(input_data=input_data, queued=True)

    # Assert — no exception was raised.
