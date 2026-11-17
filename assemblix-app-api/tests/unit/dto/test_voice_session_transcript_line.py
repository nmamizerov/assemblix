"""Unit tests: the voice-session transcript line accepts every cascade timing value."""

from __future__ import annotations

from assemblix_api.dto.responses.voice_session import VoiceSessionTranscriptLine


def test_timings_keep_fractional_and_boolean_values() -> None:
    """smartTurnProb is a probability and speculative a flag — neither may fail or be coerced."""
    # Arrange
    line = {
        "role": "assistant",
        "text": "hi",
        "timings": {"totalMs": 900, "smartTurnProb": 0.115, "speculative": True},
    }

    # Act
    parsed = VoiceSessionTranscriptLine(**line)

    # Assert
    assert parsed.timings == {"totalMs": 900, "smartTurnProb": 0.115, "speculative": True}
    assert type(parsed.timings["totalMs"]) is int
    assert type(parsed.timings["speculative"]) is bool
