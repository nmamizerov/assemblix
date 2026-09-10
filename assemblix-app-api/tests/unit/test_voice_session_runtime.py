"""Voice session runtime: one full call driven by a fake bridge."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)
from assemblix_api.realtime.hooks import TurnDispatcher
from assemblix_api.realtime.runtime import VoiceSessionRuntime


class _FakeBridge:
    """Replays a scripted provider conversation and records outbound calls."""

    input_sample_rate = 24000
    output_sample_rate = 24000

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


class _VanishedClient:
    """A browser that closes the socket in the same tick it hangs up.

    Which is what the shipped web client does: ``stop()`` sends session.stop and
    tears the socket down immediately, so every write after that raises — exactly
    as Starlette turns an OSError on a dead socket into WebSocketDisconnect.
    """

    def __init__(self) -> None:
        self.json_frames: list[dict] = []
        self._gone = False

    async def send_json(self, data: dict) -> None:
        if self._gone:
            raise RuntimeError("client is gone")
        self.json_frames.append(data)

    async def send_bytes(self, data: bytes) -> None:
        if self._gone:
            raise RuntimeError("client is gone")

    async def __aiter__(self) -> AsyncIterator[Any]:
        self._gone = True
        yield {"type": "session.stop"}


async def test_final_hook_runs_when_the_browser_is_already_gone() -> None:
    """A call the caller hung up still runs its final workflow.

    The farewell frame written to a socket nobody is listening on raises, and the
    final hook used to sit downstream of it — so a normal hangup silently produced
    no hook run at all: no execution row, no failure, nothing to notice.
    """
    # Arrange
    final_workflow_id = "22222222-2222-2222-2222-222222222222"
    runs: list[dict] = []

    async def runner(**kwargs: Any) -> None:
        runs.append(kwargs)

    runtime = VoiceSessionRuntime(
        bridge=_FakeBridge([UserTranscript(text="здравствуйте", is_final=True)]),
        client=_VanishedClient(),
        instructions="Answer calls.",
        voice="alloy",
        language="ru",
        params={},
        max_session_sec=5,
        dispatcher=TurnDispatcher(
            voice_session_id=uuid4(),
            turn_workflow_id=None,
            final_workflow_id=final_workflow_id,
            runner=runner,
        ),
    )

    # Act — the runtime may still surface the disconnect to its caller; what it
    # must not do is skip the hook on the way out.
    try:
        await runtime.run()
    except RuntimeError:
        pass

    # Assert
    assert len(runs) == 1, "the final workflow runs even though the socket is dead"
    assert str(runs[0]["workflow_id"]) == final_workflow_id
    assert runs[0]["input_data"]["voice"]["end_reason"] == "user_hangup"


async def test_speech_chars_accumulate_across_turns_and_tolerate_native_turns() -> None:
    """A call mixing turns that were synthesized with turns that were not reports
    only what a TTS provider actually spoke."""
    # Arrange
    bridge = _FakeBridge(
        [
            TurnEnded(input_tokens=1, output_tokens=2, speech_chars=12),
            TurnEnded(input_tokens=1, output_tokens=2, speech_chars=None),
            TurnEnded(input_tokens=1, output_tokens=2, speech_chars=30),
            SessionClosed(reason="completed"),
        ]
    )
    client = _FakeClient([])
    runtime = VoiceSessionRuntime(
        bridge=bridge,
        client=client,
        instructions="i",
        voice="",
        language="ru",
        params={},
        max_session_sec=5,
    )

    # Act
    await runtime.run()

    # Assert
    assert runtime.speech_chars == 42
    assert runtime.usage == (3, 6)
