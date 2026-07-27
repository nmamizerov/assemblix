from assemblix_api.enums import AgentProvider
from assemblix_api.nodes.agent_node import AgentNode


def _cfg(**overrides):
    base = {
        "provider": AgentProvider.OPENAI.value,
        "model": "gpt-4o",
        "instructions": [{"role": "system", "content": "hi"}],
    }
    base.update(overrides)
    return {"id": "a1", "type": "agent", "config": base}


def test_voice_defaults_to_text():
    # Arrange / Act
    node = AgentNode(_cfg())
    # Assert
    assert node.typed_config.output_type == "text"
    assert node.typed_config.voice is None


def test_voice_missing_voice_id_warns():
    # Arrange
    node = AgentNode(
        _cfg(output_type="voice", voice={"provider": "elevenlabs", "model": "eleven_flash_v2_5"})
    )
    # Act
    warnings = node.validate_config()
    # Assert
    assert any("voice" in w.lower() for w in warnings)


def test_streaming_voice_json_warns():
    # Arrange
    node = AgentNode(
        _cfg(
            output_type="voice",
            stream=True,
            response_format="json_object",
            voice={"provider": "elevenlabs", "model": "eleven_flash_v2_5", "voice_id": "v1"},
        )
    )
    # Act
    warnings = node.validate_config()
    # Assert
    assert any("text" in w.lower() for w in warnings)


def test_avatar_without_voice_warns():
    """Avatar output lip-syncs to our own PCM, so a voice must be selected."""
    # Arrange
    node = AgentNode(_cfg(output_type="avatar"))
    # Act
    warnings = node.validate_config()
    # Assert
    assert any("avatar" in w.lower() for w in warnings)


def test_avatar_non_realtime_voice_warns():
    """Avatar output needs the realtime path (buffered MP3 can't drive passthrough)."""
    # Arrange
    node = AgentNode(
        _cfg(
            output_type="avatar",
            voice={
                "provider": "elevenlabs",
                "model": "eleven_flash_v2_5",
                "voice_id": "v1",
                "realtime": False,
            },
        )
    )
    # Act
    warnings = node.validate_config()
    # Assert
    assert any("realtime" in w.lower() for w in warnings)


def test_avatar_realtime_voice_is_valid():
    """A realtime voice on an avatar node produces no voice/avatar warnings."""
    # Arrange
    node = AgentNode(
        _cfg(
            output_type="avatar",
            voice={
                "provider": "elevenlabs",
                "model": "eleven_flash_v2_5",
                "voice_id": "v1",
                "realtime": True,
            },
        )
    )
    # Act
    warnings = node.validate_config()
    # Assert
    assert not any("avatar" in w.lower() or "voice" in w.lower() for w in warnings)
