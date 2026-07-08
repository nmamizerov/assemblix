"""AgentNode.execute voice paths: live realtime tee + metering, and buffered single synth."""

import types

import pytest

from assemblix_api.enums import PlanTier
from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.execution.node_runner import NodeRunner
from assemblix_api.external.voice.realtime import RealtimeTTSSession
from assemblix_api.external.voice.synthesis import SynthesisResult
from assemblix_api.nodes.agent_node import AgentNode

from ._helpers import build_node, make_context, node_input


class _FakeResolver:
    async def resolve(self, **_kwargs) -> tuple[str, bool]:
        return "sk-test", True


class _FakeVoiceCred:
    async def get_voice_api_key_with_fallback(self, **_kwargs) -> tuple[str, bool]:
        return "xi-key", True


async def _noop() -> None:
    return None


def _voice_agent(*, stream: bool, model: str) -> AgentNode:
    return build_node(
        AgentNode,
        "agent",
        {
            "name": "Agent",
            "provider": "openai",
            "model": "gpt-4o",
            "instructions": [{"role": "system", "content": "You are helpful."}],
            "stream": stream,
            "output_type": "voice",
            "voice": {"provider": "elevenlabs", "model": model, "voice_id": "v1"},
        },
    )


@pytest.mark.asyncio
async def test_live_voice_tees_and_meters(mock_llm, mock_tts_ws, mocker):
    # Arrange
    mock_llm.set_stream(["Hello ", "world."])
    mock_tts_ws.script_audio([(b"\x01", None)])
    mocker.patch(
        "assemblix_api.nodes.agent_voice.RealtimeTTSSession",
        lambda **kw: RealtimeTTSSession(**{**kw, "connect": mock_tts_ws.connect}),
    )
    context = make_context(
        stream_enabled=True,
        credential_service=_FakeVoiceCred(),
        credential_resolver=_FakeResolver(),
        organization_plan=PlanTier.PRO,
        chat_history=[{"role": "user", "content": "hi"}],
    )
    mgr = DebugEventManager()
    mgr.create_stream(context.execution_id)
    runner = NodeRunner(
        tracer=types.SimpleNamespace(), debug_event_manager=mgr, db_checkpoint=_noop
    )
    node = _voice_agent(stream=True, model="eleven_flash_v2_5")
    # Act
    out = await runner.run(
        node, node_input({"message": "hi"}, context), node_id="agent-1", step_number=1
    )
    # Assert — metered as voice, no base64 blob on a live run, EOS sent
    assert out.metadata["voice_cost"] > 0
    assert "audio" not in out.data
    assert mock_tts_ws.socket.sent[-1]["text"] == ""


@pytest.mark.asyncio
async def test_buffered_voice_single_synthesis(mock_llm, mocker):
    # Arrange
    mock_llm.set_response("Hi there")
    synth = mocker.patch("assemblix_api.nodes.agent_voice.synthesize")
    synth.return_value = SynthesisResult(
        audio_bytes=b"MP3", chars=8, provider="elevenlabs", model="eleven_multilingual_v2"
    )
    context = make_context(
        stream_enabled=False,
        credential_service=_FakeVoiceCred(),
        credential_resolver=_FakeResolver(),
        organization_plan=PlanTier.PRO,
        chat_history=[{"role": "user", "content": "hi"}],
    )
    node = _voice_agent(stream=False, model="eleven_multilingual_v2")
    # Act
    out = await node.execute(node_input({"message": "hi"}, context))
    # Assert
    assert out.data["audio"]["format"] == "mp3"
    assert out.metadata["voice_cost"] > 0
    synth.assert_awaited_once()
