from assemblix_api.nodes import agent_voice
from assemblix_api.schemas.node import AgentNodeConfig, VoiceOutputConfig


def _voice_cfg():
    return AgentNodeConfig(
        provider="openai",
        model="gpt-4o",
        instructions=[{"role": "system", "content": "x"}],
        output_type="voice",
        stream=True,
        voice=VoiceOutputConfig(
            provider="elevenlabs", model="eleven_flash_v2_5", voice_id="v1", realtime=True
        ),
    )


async def _noop(_x):
    pass


async def _noop_audio(_p, _a):
    pass


def test_should_stream_voice_requires_all_conditions():
    # Arrange
    cfg = _voice_cfg()
    # Act / Assert
    assert agent_voice.should_stream_voice(cfg, on_delta=_noop, on_audio=_noop_audio) is True
    assert agent_voice.should_stream_voice(cfg, on_delta=None, on_audio=_noop_audio) is False
    text_cfg = cfg.model_copy(update={"output_type": "text"})
    assert agent_voice.should_stream_voice(text_cfg, on_delta=_noop, on_audio=_noop_audio) is False
    # Without the explicit realtime opt-in, a realtime-capable model stays buffered.
    buffered = cfg.model_copy(
        update={"voice": cfg.voice.model_copy(update={"realtime": False})}
    )
    assert (
        agent_voice.should_stream_voice(buffered, on_delta=_noop, on_audio=_noop_audio) is False
    )


def test_voice_cost_metadata():
    # Arrange
    cfg = _voice_cfg()
    # Act
    meta = agent_voice.voice_cost_metadata(cfg, chars=100, is_system_key=True)
    # Assert — dedicated voice keys so LLM `cost` on the same step is not clobbered
    assert meta["voice_used_system_key"] is True
    assert meta["chars"] == 100
    assert meta["voice_model"] == "eleven_flash_v2_5"
    assert meta["voice_cost"] > 0
    assert "cost" not in meta
