import base64

from assemblix_api.enums import PlanTier
from assemblix_api.external.voice.synthesis import SynthesisResult
from assemblix_api.nodes.end_node import EndNode

from ._helpers import build_node, make_context, node_input


class _FakeVoiceCreds:
    def __init__(self, api_key="xi-test", is_system=False):
        self._key, self._is_system = api_key, is_system

    async def get_voice_api_key_with_fallback(self, **_kwargs):
        return self._key, self._is_system


def _voice_config(max_chars=None):
    return {
        "output_mode": "custom",
        "custom_message": "Hello there",
        "output_format": "voice",
        "voice": {"provider": "elevenlabs", "model": "eleven_multilingual_v2", "voiceId": "v1"},
        "voice_max_chars": max_chars,
    }


async def _fake_synth(*, text, provider, model, voice_id, api_key):
    return SynthesisResult(audio_bytes=b"AUDIO", chars=len(text), provider=provider, model=model)


async def test_voice_output_own_key_attaches_audio(mocker) -> None:
    """Under the limit + own key → audio attached, used_system_key False, cost present."""
    # Arrange
    mocker.patch("assemblix_api.nodes.end_node.synthesize", side_effect=_fake_synth)
    node = build_node(EndNode, "end", _voice_config())
    context = make_context(credential_service=_FakeVoiceCreds(is_system=False),
                           organization_plan=PlanTier.PRO)
    # Act
    output = await node.execute(node_input({}, context))
    # Assert
    assert output.data["message"] == "Hello there"
    assert base64.b64decode(output.data["audio"]["base64"]) == b"AUDIO"
    assert output.metadata["used_system_key"] is False
    assert output.metadata["cost_kind"] == "voice"
    assert output.metadata["cost"] > 0


async def test_voice_output_system_key_flags_metadata(mocker) -> None:
    """System key → used_system_key True (drives metering)."""
    # Arrange
    mocker.patch("assemblix_api.nodes.end_node.synthesize", side_effect=_fake_synth)
    node = build_node(EndNode, "end", _voice_config())
    context = make_context(credential_service=_FakeVoiceCreds(is_system=True),
                           organization_plan=PlanTier.PRO)
    # Act
    output = await node.execute(node_input({}, context))
    # Assert
    assert output.metadata["used_system_key"] is True
    assert "audio" in output.data


async def test_over_limit_falls_back_to_text(mocker) -> None:
    """Text longer than the node limit → no synthesis, no audio, no cost."""
    # Arrange
    synth = mocker.patch("assemblix_api.nodes.end_node.synthesize", side_effect=_fake_synth)
    node = build_node(EndNode, "end", _voice_config(max_chars=3))  # "Hello there" is 11
    context = make_context(credential_service=_FakeVoiceCreds(), organization_plan=PlanTier.PRO)
    # Act
    output = await node.execute(node_input({}, context))
    # Assert
    assert output.data["message"] == "Hello there"
    assert "audio" not in output.data
    assert "cost" not in output.metadata
    synth.assert_not_called()


async def test_text_mode_unchanged_no_synthesis(mocker) -> None:
    """output_format=text (default) → no audio and synthesize never called."""
    # Arrange
    synth = mocker.patch("assemblix_api.nodes.end_node.synthesize", side_effect=_fake_synth)
    node = build_node(EndNode, "end", {"output_mode": "custom", "custom_message": "Hi"})
    context = make_context()
    # Act
    output = await node.execute(node_input({}, context))
    # Assert
    assert output.data == {"message": "Hi"}
    synth.assert_not_called()


def test_validate_config_warns_when_voice_without_voice_id() -> None:
    """Voice enabled but no voice selected → a canvas warning string."""
    # Arrange
    node = build_node(EndNode, "end", {"output_format": "voice", "voice": None})
    # Act
    warnings = node.validate_config()
    # Assert
    assert any("voice" in w.lower() for w in warnings)
