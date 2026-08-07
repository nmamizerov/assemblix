"""Voice session runtime: one full call driven by a fake bridge."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)
from assemblix_api.realtime.runtime import VoiceSessionRuntime


class _FakeBridge:
    """Replays a scripted provider conversation and records outbound calls."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.connected_with: dict | None = None
        self.sent_audio: list[bytes] = []
        self.interrupts: list[int] = []
        self.closed = False

    async def connect(self, **kwargs: Any) -> None:
        self.connected_with = kwargs

    async def send_audio(self, pcm: bytes) -> None:
        self.sent_audio.append(pcm)

    async def interrupt(self, *, audio_end_ms: int) -> None:
        self.interrupts.append(audio_end_ms)

    def events(self) -> AsyncIterator[Any]:
        async def _iter() -> AsyncIterator[Any]:
            for event in self._events:
                yield event

        return _iter()

    async def close(self) -> None:
        self.closed = True


class _FakeClient:
    """Feeds inbound frames once, then blocks until the bridge side finishes."""

    def __init__(self, inbound: list[Any]) -> None:
        self._inbound = inbound
        self.json_frames: list[dict] = []
        self.audio_frames: list[bytes] = []

    async def send_json(self, data: dict) -> None:
        self.json_frames.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.audio_frames.append(data)

    async def __aiter__(self) -> AsyncIterator[Any]:
        for frame in self._inbound:
            yield frame


async def test_runtime_drives_a_full_call() -> None:
    """Audio flows both ways, a barge-in truncates the provider, transcript
    accumulates, and the session ends on the provider's close."""
    # Arrange
    one_ms_of_audio = b"\x00\x00" * 24  # 24 samples @ 24 kHz == 1 ms
    bridge = _FakeBridge(
        [
            UserTranscript(text="прив", is_final=False),
            UserTranscript(text="привет", is_final=True),
            AudioDelta(pcm=one_ms_of_audio * 10),
            AgentTranscript(text="Здравствуйте", is_final=True),
            SpeechStarted(),
            TurnEnded(input_tokens=120, output_tokens=45),
            SessionClosed(reason="completed"),
        ]
    )
    client = _FakeClient([b"microphone-frame", {"type": "noop"}])
    runtime = VoiceSessionRuntime(
        bridge=bridge,
        client=client,
        instructions="You are a receptionist.",
        voice="alloy",
        language="ru",
        params={"silence_duration_ms": 300},
        max_session_sec=5,
    )

    # Act
    reason = await runtime.run()

    # Assert — the session opened with the agent's configuration
    assert reason == "completed"
    assert bridge.connected_with == {
        "instructions": "You are a receptionist.",
        "voice": "alloy",
        "language": "ru",
        "params": {"silence_duration_ms": 300},
    }

    # Assert — audio crossed in both directions
    assert bridge.sent_audio == [b"microphone-frame"]
    assert client.audio_frames == [one_ms_of_audio * 10]

    # Assert — barge-in truncated the provider at what was actually played
    assert bridge.interrupts == [10]
    assert {"type": "speech.started"} in client.json_frames

    # Assert — only final transcript lines are kept
    assert runtime.transcript == [
        {"role": "user", "text": "привет"},
        {"role": "assistant", "text": "Здравствуйте"},
    ]

    # Assert — the client was told how the session opened and closed
    assert client.json_frames[0] == {
        "type": "session.ready",
        "inputSampleRate": 24000,
        "outputSampleRate": 24000,
    }
    assert client.json_frames[-1] == {"type": "session.closed", "reason": "completed"}
    assert bridge.closed is True
