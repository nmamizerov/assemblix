"""OpenAI realtime bridge: event normalization, error surfacing, outbound calls."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from assemblix_api.external.voice.bridge import (
    AgentTranscript,
    AudioDelta,
    BridgeError,
    SessionClosed,
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
        SimpleNamespace(
            type="response.done",
            response=SimpleNamespace(usage=SimpleNamespace(input_tokens=120, output_tokens=45)),
        ),
    ]
    bridge = OpenAIRealtimeBridge(
        api_key="sk-test",
        model="gpt-realtime-2.1",
        connect_factory=lambda **_: _fake_connection(server_events, recorder),
    )
    await bridge.connect(instructions="be nice", voice="alloy", language="ru", params={})

    # Act
    received = [event async for event in bridge.events()]

    # Assert — the vocabulary, in order, terminated by the connection ending
    assert received == [
        SpeechStarted(),
        UserTranscript(text="при", is_final=False),
        UserTranscript(text="привет", is_final=True),
        AudioDelta(pcm=b"\x00\x01\x02\x03"),
        AgentTranscript(text="Здрав", is_final=False),
        AgentTranscript(text="Здравствуйте", is_final=True),
        TurnEnded(input_tokens=120, output_tokens=45),
        SessionClosed(reason="closed"),
    ]


async def test_provider_error_surfaces_instead_of_being_swallowed() -> None:
    """An `error` server event becomes a BridgeError; the iterator does not raise."""
    # Arrange
    recorder = _Recorder()
    server_events = [
        SimpleNamespace(
            type="error",
            error=SimpleNamespace(
                code="invalid_request_error", message="bad voice", type="invalid_request_error"
            ),
        ),
        SimpleNamespace(type="response.done", response=SimpleNamespace(usage=None)),
    ]
    bridge = OpenAIRealtimeBridge(
        api_key="sk-test",
        model="gpt-realtime-2.1",
        connect_factory=lambda **_: _fake_connection(server_events, recorder),
    )
    await bridge.connect(instructions="x", voice="alloy", language="ru", params={})

    # Act
    received = [event async for event in bridge.events()]

    # Assert — a request-level error is not fatal; the terminal event still arrives
    assert received[0] == BridgeError(
        code="invalid_request_error", message="bad voice", is_fatal=False
    )
    assert received[1] == TurnEnded()
    assert received[2] == SessionClosed(reason="closed")


async def test_outbound_calls_configure_the_session_and_drive_audio() -> None:
    """connect() configures instructions/voice/format/VAD; send_audio appends base64
    PCM16; interrupt() cancels the response and truncates the in-flight assistant
    item's audio at the point the user actually heard it."""
    # Arrange
    recorder = _Recorder()
    server_events = [
        SimpleNamespace(
            type="response.output_item.added",
            item=SimpleNamespace(id="item_abc", role="assistant"),
        ),
    ]
    bridge = OpenAIRealtimeBridge(
        api_key="sk-test",
        model="gpt-realtime-2.1",
        connect_factory=lambda **_: _fake_connection(server_events, recorder),
    )

    # Act
    await bridge.connect(
        instructions="You are a receptionist.",
        voice="alloy",
        language="ru",
        params={"silence_duration_ms": 300},
    )
    await bridge.send_audio(b"\x00\x01\x02\x03")
    # Drain the response.output_item.added event so the bridge learns the item id
    # it needs in order to truncate.
    [_ async for _ in bridge.events()]
    await bridge.interrupt(audio_end_ms=750)

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

    # Assert — interruption cancels the response, then truncates on the WebSocket
    # transport (output_audio_buffer.clear is WebRTC/SIP-only and does nothing here)
    assert recorder.calls[2] == ("response.cancel", {})
    assert recorder.calls[3] == (
        "conversation.item.truncate",
        {"item_id": "item_abc", "content_index": 0, "audio_end_ms": 750},
    )
