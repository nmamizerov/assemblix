import pytest

from assemblix_api.execution.voice_gate import ensure_audio_run_is_synchronous


def test_audio_run_rejected_when_queued() -> None:
    with pytest.raises(ValueError, match="synchronous"):
        ensure_audio_run_is_synchronous(input_data={"input_type": "audio"}, queued=True)


def test_text_run_allowed_when_queued() -> None:
    ensure_audio_run_is_synchronous(input_data={"input_type": "text"}, queued=True)  # no raise
