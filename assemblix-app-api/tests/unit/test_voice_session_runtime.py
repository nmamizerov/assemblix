"""Voice session runtime: one full call driven by a fake bridge."""

from __future__ import annotations

import asyncio
import time
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
    TurnTimings,
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


def _recording_dispatcher(order: list[str]) -> TurnDispatcher:
    async def runner(**kwargs: Any) -> None:
        order.append("final_hook")

    return TurnDispatcher(
        voice_session_id=uuid4(),
        turn_workflow_id=None,
        final_workflow_id="22222222-2222-2222-2222-222222222222",
        runner=runner,
    )


async def test_on_stopped_runs_after_bridge_close_and_before_the_final_hook() -> None:
    # Arrange
    order: list[str] = []

    class _Bridge(_FakeBridge):
        async def close(self) -> None:
            order.append("bridge_close")

    async def on_stopped() -> None:
        order.append("on_stopped")

    # Act
    await _runtime(
        _Bridge([SessionClosed(reason="completed")]),
        _PlaybackClient([], heard_ms=None),
        dispatcher=_recording_dispatcher(order),
        on_stopped=on_stopped,
    ).run()

    # Assert
    assert order == ["bridge_close", "on_stopped", "final_hook"]


async def test_on_stopped_failure_does_not_cost_the_final_hook() -> None:
    # Arrange
    order: list[str] = []

    async def on_stopped() -> None:
        raise RuntimeError("room teardown failed")

    # Act
    reason = await _runtime(
        _FakeBridge([SessionClosed(reason="completed")]),
        _PlaybackClient([], heard_ms=None),
        dispatcher=_recording_dispatcher(order),
        on_stopped=on_stopped,
    ).run()

    # Assert
    assert reason == "completed"
    assert order == ["final_hook"]


async def test_cascade_timings_are_closed_at_first_audio_and_stored_on_the_reply() -> None:
    ended = time.monotonic() - 0.9
    script = [
        UserTranscript(text="привет", is_final=True),
        TurnTimings(speech_ended_at=ended, eou_ms=224, stt_final_ms=80, brain_first_token_ms=350),
        AgentTranscript(text="Здравствуйте", is_final=False),
        AudioDelta(pcm=b"\x00" * 640),
        AgentTranscript(text="Здравствуйте", is_final=True),
        TurnEnded(),
        SessionClosed(reason="done"),
    ]
    client = _FakeClient([])
    runtime = _runtime(_FakeBridge(script), client)

    await runtime.run()

    timings = [m for m in client.json_frames if m.get("type") == "turn.timings"]
    assert len(timings) == 1
    event = timings[0]
    assert event["eouMs"] == 224 and event["sttFinalMs"] == 80 and event["brainFirstTokenMs"] == 350
    assert event["totalMs"] >= 900
    assert event["ttsFirstAudioMs"] == event["totalMs"] - 224 - 80 - 350
    assistant = [line for line in runtime.transcript if line["role"] == "assistant"]
    assert assistant[0]["timings"] == {
        **{k: v for k, v in event.items() if k != "type"},
        "ttsGapMaxMs": 0,
    }
    assert "timings" not in runtime.transcript[0]


async def test_a_cascade_turn_reports_its_timings_once_despite_a_live_microphone() -> None:
    """The browser streams mic audio throughout the reply; later audio packets of a
    measured turn must not emit a second, inbound-audio based timing."""
    first_audio_out = asyncio.Event()
    mic_sent = asyncio.Event()

    class _MicClient(_FakeClient):
        async def send_bytes(self, data: bytes) -> None:
            await super().send_bytes(data)
            first_audio_out.set()

        async def __aiter__(self) -> AsyncIterator[Any]:
            await first_audio_out.wait()
            yield b"mic-while-agent-speaks"
            await asyncio.Event().wait()

    class _MicBridge(_FakeBridge):
        async def send_audio(self, pcm: bytes) -> None:
            await super().send_audio(pcm)
            mic_sent.set()

        def events(self) -> AsyncIterator[Any]:
            async def _iter() -> AsyncIterator[Any]:
                yield TurnTimings(
                    speech_ended_at=time.monotonic(),
                    eou_ms=10,
                    stt_final_ms=20,
                    brain_first_token_ms=30,
                )
                yield AudioDelta(pcm=b"\x00" * 640)
                await mic_sent.wait()
                yield AudioDelta(pcm=b"\x00" * 640)
                yield AgentTranscript(text="Здравствуйте", is_final=True)
                yield TurnEnded()
                yield SessionClosed(reason="done")

            return _iter()

    client = _MicClient([])

    await _runtime(_MicBridge([]), client).run()

    timings = [m for m in client.json_frames if m.get("type") == "turn.timings"]
    assert len(timings) == 1
    assert timings[0]["firstAudioMs"] == timings[0]["totalMs"]


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _ClockedBridge(_FakeBridge):
    """A scripted bridge where a float in the script advances the clock, in seconds."""

    def __init__(self, events: list[Any], clock: _Clock, *, late: bool) -> None:
        super().__init__(events)
        self._clock = clock
        if late:
            self.accepts_late_interrupt = True

    def events(self) -> AsyncIterator[Any]:
        async def _iter() -> AsyncIterator[Any]:
            for event in self._events:
                if isinstance(event, float):
                    self._clock.now += event
                else:
                    yield event

        return _iter()


class _BrowserClient(_FakeClient):
    """The plain WebSocket path: playback lives in the browser, so nothing is reported."""

    async def __aiter__(self) -> AsyncIterator[Any]:
        await asyncio.Event().wait()
        yield b""


_ONE_SECOND = AudioDelta(pcm=b"\x00\x00" * 24000)


async def _barge_in(script: list[Any], *, late: bool) -> list[int]:
    clock = _Clock()
    bridge = _ClockedBridge([*script, SessionClosed(reason="done")], clock, late=late)
    await _runtime(bridge, _BrowserClient([]), clock=clock).run()
    return bridge.interrupts


async def test_a_barge_in_after_turn_end_truncates_a_reply_still_playing() -> None:
    """The reply was fully sent and the turn ended, but the browser is still playing
    it: a bridge that accepts late interrupts is told how much was heard."""
    # Arrange
    script = [_ONE_SECOND, TurnEnded(), 0.4, SpeechStarted()]

    # Act
    interrupts = await _barge_in(script, late=True)

    # Assert
    assert interrupts == [400]


async def test_speech_after_the_reply_finished_playing_interrupts_nothing() -> None:
    # Arrange
    script = [_ONE_SECOND, TurnEnded(), 1.5, SpeechStarted()]

    # Act
    interrupts = await _barge_in(script, late=True)

    # Assert
    assert interrupts == []


async def test_a_barge_in_mid_turn_reports_wall_clock_playback_to_a_late_bridge() -> None:
    """Audio forwarded is not audio heard: the browser buffers ahead of playback."""
    # Arrange
    script = [_ONE_SECOND, 0.3, SpeechStarted()]

    # Act
    interrupts = await _barge_in(script, late=True)

    # Assert
    assert interrupts == [300]


async def test_playback_tracking_restarts_with_the_next_turn() -> None:
    # Arrange — the first turn played out long ago; the second has just begun
    script = [_ONE_SECOND, TurnEnded(), 5.0, _ONE_SECOND, TurnEnded(), 0.2, SpeechStarted()]

    # Act
    interrupts = await _barge_in(script, late=True)

    # Assert
    assert interrupts == [200]


async def test_a_bridge_without_late_interrupts_behaves_as_before() -> None:
    """Speech-to-speech providers keep today's contract: nothing after TurnEnded,
    and the forwarded duration during a turn."""
    # Arrange
    after_turn = [_ONE_SECOND, TurnEnded(), 0.4, SpeechStarted()]
    mid_turn = [_ONE_SECOND, 0.3, SpeechStarted()]

    # Act
    after_turn_interrupts = await _barge_in(after_turn, late=False)
    mid_turn_interrupts = await _barge_in(mid_turn, late=False)

    # Assert
    assert after_turn_interrupts == []
    assert mid_turn_interrupts == [1000]


async def test_the_longest_silence_inside_a_cascade_reply_is_stored_on_its_timings() -> None:
    """Audio arriving after the forwarded audio would have finished playing is a gap
    the caller heard; the longest one per turn lands on the reply's timings."""
    # Arrange
    clock = _Clock()
    script = [
        UserTranscript(text="привет", is_final=True),
        TurnTimings(
            speech_ended_at=time.monotonic(), eou_ms=1, stt_final_ms=1, brain_first_token_ms=1
        ),
        _ONE_SECOND,
        1.2,  # the first second plays out, then 0.2 s of silence
        _ONE_SECOND,
        0.1,  # still covered by buffered audio
        _ONE_SECOND,
        2.4,  # 1.9 s of buffered audio left, then 0.5 s of silence
        _ONE_SECOND,
        AgentTranscript(text="Здравствуйте", is_final=True),
        TurnEnded(),
        SessionClosed(reason="done"),
    ]
    bridge = _ClockedBridge(script, clock, late=False)
    runtime = _runtime(bridge, _BrowserClient([]), clock=clock)

    # Act
    await runtime.run()

    # Assert
    assistant = [line for line in runtime.transcript if line["role"] == "assistant"]
    assert assistant[0]["timings"]["ttsGapMaxMs"] == 500
