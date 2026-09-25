"""Voice session runtime: one full call driven by a fake bridge."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest

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

    media = "ws"

    def __init__(self, inbound: list[Any]) -> None:
        self._inbound = inbound
        self.json_frames: list[dict] = []
        self.audio_frames: list[bytes] = []

    async def send_json(self, data: dict) -> None:
        self.json_frames.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.audio_frames.append(data)

    async def interrupt_playback(self) -> int | None:
        return None

    async def end_of_utterance(self) -> None: ...

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
        "media": "ws",
    }
    assert client.json_frames[-1] == {"type": "session.closed", "reason": "completed"}
    assert bridge.closed is True


class _VanishedClient:
    """A browser that closes the socket in the same tick it hangs up.

    Which is what the shipped web client does: ``stop()`` sends session.stop and
    tears the socket down immediately, so every write after that raises — exactly
    as Starlette turns an OSError on a dead socket into WebSocketDisconnect.
    """

    media = "ws"

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

    async def interrupt_playback(self) -> int | None:
        return None

    async def end_of_utterance(self) -> None: ...

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


class _PlaybackClient(_FakeClient):
    """A channel whose playback runs behind generation, like an avatar."""

    media = "livekit"

    def __init__(self, inbound: list[Any], heard_ms: int | None) -> None:
        super().__init__(inbound)
        self._heard_ms = heard_ms
        self.interrupts = 0
        self.utterance_ends = 0

    async def interrupt_playback(self) -> int | None:
        self.interrupts += 1
        return self._heard_ms

    async def end_of_utterance(self) -> None:
        self.utterance_ends += 1

    async def __aiter__(self) -> AsyncIterator[Any]:
        for frame in self._inbound:
            yield frame
        # Mirrors _FakeClient in test_voice_session_hooks.py: block instead of
        # ending, so the client pump never wins the run() race against the
        # scripted bridge events.
        await asyncio.sleep(3600)
        yield b""


def _runtime(bridge: Any, client: Any, **kwargs: Any) -> VoiceSessionRuntime:
    return VoiceSessionRuntime(
        bridge=bridge,
        client=client,
        instructions="x",
        voice="alloy",
        language="ru",
        params={},
        max_session_sec=5,
        **kwargs,
    )


async def test_barge_in_during_playback_truncates_after_generation_ended() -> None:
    bridge = _FakeBridge(
        [
            AudioDelta(pcm=b"\x00\x00" * 24000),  # 1 s generated
            TurnEnded(),  # generation done, avatar still talking
            SpeechStarted(),
            SessionClosed(reason="completed"),
        ]
    )
    client = _PlaybackClient([], heard_ms=420)

    await _runtime(bridge, client).run()

    assert client.utterance_ends == 1
    assert client.interrupts == 1
    assert bridge.interrupts == [420]


async def test_nothing_playing_and_nothing_generating_interrupts_nothing() -> None:
    bridge = _FakeBridge([SpeechStarted(), SessionClosed(reason="completed")])
    client = _PlaybackClient([], heard_ms=None)

    await _runtime(bridge, client).run()

    assert bridge.interrupts == []


async def test_session_ready_names_the_media_plane() -> None:
    bridge = _FakeBridge([SessionClosed(reason="completed")])
    client = _PlaybackClient([], heard_ms=None)

    await _runtime(bridge, client).run()

    assert client.json_frames[0]["type"] == "session.ready"
    assert client.json_frames[0]["media"] == "livekit"


async def test_prepare_runs_before_session_ready_and_its_failure_propagates() -> None:
    order: list[str] = []

    class _Bridge(_FakeBridge):
        async def connect(self, **kwargs: Any) -> None:
            order.append("connect")

    async def prepare() -> None:
        order.append("prepare")

    client = _PlaybackClient([], heard_ms=None)
    await _runtime(_Bridge([SessionClosed(reason="completed")]), client, prepare=prepare).run()
    assert sorted(order) == ["connect", "prepare"]
    assert client.json_frames[0]["type"] == "session.ready"

    async def failing() -> None:
        raise RuntimeError("avatar failed")

    failed_client = _PlaybackClient([], heard_ms=None)
    with pytest.raises(RuntimeError):
        await _runtime(_FakeBridge([]), failed_client, prepare=failing).run()
    assert failed_client.json_frames == []


async def test_prepare_failure_closes_the_bridge_and_skips_session_ready() -> None:
    bridge = _FakeBridge([])

    async def failing() -> None:
        raise RuntimeError("avatar failed")

    client = _PlaybackClient([], heard_ms=None)
    with pytest.raises(RuntimeError):
        await _runtime(bridge, client, prepare=failing).run()

    assert bridge.closed is True
    assert client.json_frames == []


async def test_connect_failure_cancels_a_slow_prepare() -> None:
    cancelled = False

    class _FailingBridge(_FakeBridge):
        async def connect(self, **kwargs: Any) -> None:
            raise RuntimeError("connect failed")

    async def slow_prepare() -> None:
        nonlocal cancelled
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled = True
            raise

    client = _PlaybackClient([], heard_ms=None)
    with pytest.raises(RuntimeError, match="connect failed"):
        await _runtime(_FailingBridge([]), client, prepare=slow_prepare).run()

    assert cancelled is True


async def test_cancelling_run_while_joining_cancels_connect_and_prepare() -> None:
    connect_cancelled = False
    prepare_cancelled = False

    class _SlowBridge(_FakeBridge):
        async def connect(self, **kwargs: Any) -> None:
            nonlocal connect_cancelled
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                connect_cancelled = True
                raise

    async def slow_prepare() -> None:
        nonlocal prepare_cancelled
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            prepare_cancelled = True
            raise

    bridge = _SlowBridge([])
    client = _PlaybackClient([], heard_ms=None)
    run_task = asyncio.create_task(_runtime(bridge, client, prepare=slow_prepare).run())
    # Give both children a chance to actually start their sleep before cancelling.
    await asyncio.sleep(0.01)
    run_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await run_task

    assert connect_cancelled is True
    assert prepare_cancelled is True
    assert bridge.closed is True
