from assemblix_api.nodes.end_node import EndNode
from assemblix_api.schemas.node import EndNodeConfig


def test_end_node_has_no_synthesis():
    # Arrange / Act / Assert — voice synthesis moved to the AGENT node.
    assert not hasattr(EndNode, "_synthesize_into")


def test_voice_removed_from_schema_but_legacy_config_loads():
    # Arrange / Act — legacy voice keys must not raise (DTOModel extra="allow"); the fields
    # are no longer part of the END schema.
    cfg = EndNodeConfig(
        **{
            "output_mode": "last_agent",
            "output_format": "voice",
            "voice": {"provider": "elevenlabs", "model": "m"},
        }
    )
    # Assert
    assert cfg.output_mode == "last_agent"
    assert "output_format" not in EndNodeConfig.model_fields
    assert "voice" not in EndNodeConfig.model_fields
