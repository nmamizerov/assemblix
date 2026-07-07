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
