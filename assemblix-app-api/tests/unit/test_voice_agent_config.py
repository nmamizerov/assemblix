import pytest
from pydantic import ValidationError

from assemblix_api.schemas.voice_agent import VoiceAgentConfig

_INSTRUCTIONS = [{"role": "system", "content": "Talk."}]
_VOICE = {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"}
_TTS = {"provider": "yandex", "model": "yandex-tts-v3-chunk", "voiceId": "alena", "realtime": True}
_CASCADE = {
    "stt": {"provider": "yandex"},
    "brain": {"type": "prompt", "provider": "gemini", "model": "gemini-2.5-flash-lite"},
}


def test_stored_config_without_mode_loads_as_realtime() -> None:
    config = VoiceAgentConfig(instructions=_INSTRUCTIONS, voice=_VOICE)

    assert config.mode == "realtime"
    assert config.cascade is None


def test_cascade_config_with_defaults() -> None:
    config = VoiceAgentConfig(
        instructions=_INSTRUCTIONS, mode="cascade", tts=_TTS, cascade=_CASCADE
    )

    assert config.voice is None
    assert config.cascade is not None
    assert config.cascade.turn.min_silence_ms == 200
    assert config.cascade.turn.max_silence_ms == 1500
    assert config.cascade.brain.history_turns == 40


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"mode": "realtime"}, "needs a `voice`"),
        (
            {"mode": "realtime", "voice": _VOICE, "cascade": _CASCADE},
            "only valid with mode='cascade'",
        ),
        ({"mode": "cascade", "tts": _TTS}, "needs a `cascade` block"),
        ({"mode": "cascade", "cascade": _CASCADE}, "needs `tts`"),
    ],
)
def test_blocks_must_match_mode(payload: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        VoiceAgentConfig(instructions=_INSTRUCTIONS, **payload)


def test_turn_bounds_are_enforced() -> None:
    bad = {**_CASCADE, "turn": {"minSilenceMs": 2000, "maxSilenceMs": 1500}}

    with pytest.raises(ValidationError, match="max_silence_ms"):
        VoiceAgentConfig(instructions=_INSTRUCTIONS, mode="cascade", tts=_TTS, cascade=bad)
