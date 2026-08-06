"""OpenAI realtime bridge: event normalization, error surfacing, outbound calls."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from assemblix_api.external.voice.bridge import (
    AgentTranscript,
    AudioDelta,
    BridgeError,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)
from assemblix_api.external.voice.openai_bridge import OpenAIRealtimeBridge


class _Recorder:
    """Records every outbound resource call as (name, kwargs)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def resource(self, name: str) -> Any:
        async def _call(**kwargs: Any) -> None:
            self.calls.append((name, kwargs))

        return _call


def _fake_connection(events: list[Any], recorder: _Recorder) -> Any:
    """A stand-in for AsyncRealtimeConnection with the same attribute shape."""

    class _Conn:
        session = SimpleNamespace(update=recorder.resource("session.update"))
        response = SimpleNamespace(cancel=recorder.resource("response.cancel"))
        input_audio_buffer = SimpleNamespace(append=recorder.resource("input_audio_buffer.append"))
        output_audio_buffer = SimpleNamespace(clear=recorder.resource("output_audio_buffer.clear"))
        conversation = SimpleNamespace(
            item=SimpleNamespace(truncate=recorder.resource("conversation.item.truncate"))
        )

        async def close(self) -> None:
            recorder.calls.append(("close", {}))

        async def __aiter__(self):
            for event in events:
                yield event

    return _Conn()


async def test_normalizes_a_provider_turn_into_bridge_events() -> None:
    """A realistic server-event sequence maps to the bridge vocabulary, in order,
    and an unknown event type is ignored rather than breaking the loop."""
    # Arrange
    recorder = _Recorder()
    server_events = [
        SimpleNamespace(type="session.created"),
        SimpleNamespace(type="input_audio_buffer.speech_started"),
        SimpleNamespace(type="conversation.item.input_audio_transcription.delta", delta="при"),
        SimpleNamespace(
            type="conversation.item.input_audio_transcription.completed", transcript="привет"
        ),
        SimpleNamespace(type="response.output_audio.delta", delta="AAECAw=="),
        SimpleNamespace(type="response.output_audio_transcript.delta", delta="Здрав"),
        SimpleNamespace(type="response.output_audio_transcript.done", transcript="Здравствуйте"),
        SimpleNamespace(type="some.future.event.we.do.not.know"),
        SimpleNamespace(type="response.done"),
    ]
    bridge = OpenAIRealtimeBridge(
        api_key="sk-test",
        model="gpt-realtime-2.1",
        connect_factory=lambda **_: _fake_connection(server_events, recorder),
    )
    await bridge.connect(instructions="be nice", voice="alloy", language="ru", params={})

    # Act
    received = [event async for event in bridge.events()]

    # Assert — the vocabulary, in order
    assert received == [
        SpeechStarted(),
        UserTranscript(text="при", is_final=False),
        UserTranscript(text="привет", is_final=True),
        AudioDelta(pcm=b"\x00\x01\x02\x03"),
        AgentTranscript(text="Здрав", is_final=False),
        AgentTranscript(text="Здравствуйте", is_final=True),
        TurnEnded(),
    ]


async def test_provider_error_surfaces_instead_of_being_swallowed() -> None:
    """An `error` server event becomes a BridgeError; the iterator does not raise."""
    # Arrange
    recorder = _Recorder()
    server_events = [
        SimpleNamespace(
            type="error",
            error=SimpleNamespace(code="invalid_request_error", message="bad voice"),
        ),
        SimpleNamespace(type="response.done"),
    ]
    bridge = OpenAIRealtimeBridge(
        api_key="sk-test",
        model="gpt-realtime-2.1",
        connect_factory=lambda **_: _fake_connection(server_events, recorder),
    )
    await bridge.connect(instructions="x", voice="alloy", language="ru", params={})

    # Act
    received = [event async for event in bridge.events()]

    # Assert
    assert received[0] == BridgeError(code="invalid_request_error", message="bad voice")
    assert received[1] == TurnEnded()


async def test_outbound_calls_configure_the_session_and_drive_audio() -> None:
    """connect() configures instructions/voice/format/VAD; send_audio appends base64
    PCM16; interrupt() both cancels the response and clears the output buffer."""
    # Arrange
    recorder = _Recorder()
    bridge = OpenAIRealtimeBridge(
        api_key="sk-test",
        model="gpt-realtime-2.1",
        connect_factory=lambda **_: _fake_connection([], recorder),
    )

    # Act
    await bridge.connect(
        instructions="You are a receptionist.",
        voice="alloy",
        language="ru",
        params={"silence_duration_ms": 300},
    )
    await bridge.send_audio(b"\x00\x01\x02\x03")
    await bridge.interrupt()

    # Assert — session configuration
    name, kwargs = recorder.calls[0]
    assert name == "session.update"
    session = kwargs["session"]
    assert session["instructions"] == "You are a receptionist."
    assert session["audio"]["output"]["voice"] == "alloy"
    assert session["audio"]["input"]["turn_detection"]["type"] == "server_vad"
    assert session["audio"]["input"]["turn_detection"]["silence_duration_ms"] == 300

    # Assert — audio is appended base64-encoded
    assert recorder.calls[1] == ("input_audio_buffer.append", {"audio": "AAECAw=="})

    # Assert — interruption is two-sided on the provider
    assert [name for name, _ in recorder.calls[2:]] == [
        "response.cancel",
        "output_audio_buffer.clear",
    ]
