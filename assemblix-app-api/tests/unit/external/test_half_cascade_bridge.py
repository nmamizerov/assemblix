"""Half-cascade bridge: the model writes, a TTS provider speaks."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    BridgeError,
    BridgeEvent,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)
from assemblix_api.external.voice.conversation.half_cascade import HalfCascadeBridge
from assemblix_api.external.voice.speech_out import SpeechOutput


class _FakeInner:
    """A conversation bridge whose event stream the test scripts."""

    input_sample_rate = 24000
    output_sample_rate = 24000

    def __init__(self, script: list[BridgeEvent]) -> None:
        self._script = script
        self.connect_kwargs: dict | None = None
        self.interrupts: list[int] = []
        self.closed = False

    async def connect(self, **kwargs: Any) -> None:
        self.connect_kwargs = kwargs

    async def send_audio(self, pcm: bytes) -> None: ...

    async def interrupt(self, *, audio_end_ms: int) -> None:
        self.interrupts.append(audio_end_ms)

    async def events(self) -> AsyncIterator[BridgeEvent]:
        for event in self._script:
            yield event
            await asyncio.sleep(0)

    async def close(self) -> None:
        self.closed = True


class _FakeTTS:
    """A streaming TTS session recording what it was told to say."""

    instances: list[_FakeTTS] = []

    def __init__(self, on_audio: Any, on_error: Any) -> None:
        self.on_audio = on_audio
        self.on_error = on_error
        self.opened = False
        self.sent: list[str] = []
        self.flushed = False
        self.aborted = False
        _FakeTTS.instances.append(self)

    async def open(self) -> None:
        self.opened = True

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def flush_and_close(self) -> int:
        self.flushed = True
        return sum(len(part) for part in self.sent)

    async def aclose(self) -> None:
        self.aborted = True


def _target() -> SpeechOutput:
    return SpeechOutput(
        provider="elevenlabs",
        model="eleven_flash_v2_5",
        voice_id="v1",
        api_key="k",
        uses_system_key=True,
    )


def _bridge(inner: _FakeInner) -> HalfCascadeBridge:
    _FakeTTS.instances.clear()
    return HalfCascadeBridge(
        inner=inner,
        speech_out=_target(),
        output_sample_rate=16000,
        open_stream=lambda _out, on_audio, on_error, **_kwargs: _FakeTTS(on_audio, on_error),
    )


async def test_a_turn_is_written_by_the_model_and_spoken_by_the_provider() -> None:
    """Across one full turn: the model is put in text mode, the TTS session opens
    only once text exists, every delta is both forwarded and spoken, provider audio
    surfaces as AudioDelta, and the turn reports what it cost to say."""
    # Arrange
    inner = _FakeInner(
        [
            UserTranscript(text="привет", is_final=True),
            AgentTranscript(text="Здрав", is_final=False),
            AgentTranscript(text="ствуйте", is_final=False),
            # The provider repeats the whole reply on the final event.
            AgentTranscript(text="Здравствуйте", is_final=True),
            TurnEnded(input_tokens=10, output_tokens=5),
            SessionClosed(reason="closed"),
        ]
    )
    bridge = _bridge(inner)

    # Act
    await bridge.connect(instructions="i", voice="", language="ru", params={})
    seen: list[BridgeEvent] = []
    async for event in bridge.events():
        seen.append(event)
        if isinstance(event, AgentTranscript) and not event.is_final:
            await _FakeTTS.instances[0].on_audio(b"\x01\x02", None)
    await bridge.close()

    # Assert
    assert inner.connect_kwargs is not None and inner.connect_kwargs["text_output"] is True
    assert bridge.input_sample_rate == 24000
    assert bridge.output_sample_rate == 16000
    tts = _FakeTTS.instances[0]
    assert tts.sent == ["Здрав", "ствуйте"]
    assert tts.flushed is True
    assert AudioDelta(pcm=b"\x01\x02") in seen
    assert AgentTranscript(text="Здравствуйте", is_final=True) in seen
    turn = next(e for e in seen if isinstance(e, TurnEnded))
    assert turn.speech_chars == len("Здравствуйте")
    assert turn.input_tokens == 10
    assert inner.closed is True


async def test_barge_in_silences_the_turn_and_a_dead_provider_ends_the_call() -> None:
    """A barge-in aborts the in-flight speech, cancels the model turn and discards
    text the model had already committed to; the next turn speaks normally; and a
    TTS transport failure surfaces as a fatal error rather than silence."""
    # Arrange
    inner = _FakeInner(
        [
            AgentTranscript(text="Длинный ", is_final=False),
            SpeechStarted(),
            AgentTranscript(text="хвост отменённой реплики", is_final=True),
            TurnEnded(),
            AgentTranscript(text="Слушаю", is_final=True),
            TurnEnded(),
        ]
    )
    bridge = _bridge(inner)

    # Act
    await bridge.connect(instructions="i", voice="", language="ru", params={})
    seen: list[BridgeEvent] = []
    async for event in bridge.events():
        seen.append(event)
        if isinstance(event, SpeechStarted):
            await bridge.interrupt(audio_end_ms=400)
        if isinstance(event, TurnEnded) and len(_FakeTTS.instances) == 2:
            await _FakeTTS.instances[1].on_error("websocket closed")
        if isinstance(event, BridgeError):
            break
    await bridge.close()

    # Assert
    aborted, second = _FakeTTS.instances[0], _FakeTTS.instances[1]
    assert aborted.sent == ["Длинный "]
    assert aborted.aborted is True
    assert inner.interrupts == [400]
    assert second.sent == ["Слушаю"]
    assert len(_FakeTTS.instances) == 2
    error = next(e for e in seen if isinstance(e, BridgeError))
    assert error.is_fatal is True


async def test_the_user_starting_to_speak_is_not_a_barge_in_by_itself() -> None:
    """SpeechStarted is plain voice-activity detection: it precedes every turn,
    not just an interruption. Only speech already in flight can be cancelled —
    otherwise the first thing the caller says silences the agent for the rest of
    the call."""
    # Arrange
    inner = _FakeInner(
        [
            SpeechStarted(),
            UserTranscript(text="привет", is_final=True),
            AgentTranscript(text="Здравствуйте", is_final=True),
            TurnEnded(),
            SpeechStarted(),
            AgentTranscript(text="Слушаю", is_final=True),
            TurnEnded(),
            SessionClosed(reason="completed"),
        ]
    )
    bridge = _bridge(inner)

    # Act
    await bridge.connect(instructions="i", voice="", language="ru", params={})
    async for _event in bridge.events():
        pass
    await bridge.close()

    # Assert
    assert [tts.sent for tts in _FakeTTS.instances] == [["Здравствуйте"], ["Слушаю"]]


async def test_only_the_unspoken_remainder_of_a_reply_is_sent_to_the_provider() -> None:
    """Bridges disagree about what AgentTranscript.text means: OpenAI streams
    deltas and then repeats the whole reply on the final event, while Gemini
    accumulates from the start. Speaking every event verbatim says the reply
    twice, so only the part not yet spoken may reach the synthesizer."""
    # Arrange — the OpenAI shape: deltas, then the complete text on the final event
    openai_shaped = _FakeInner(
        [
            AgentTranscript(text="Здрав", is_final=False),
            AgentTranscript(text="ствуйте", is_final=False),
            AgentTranscript(text="Здравствуйте", is_final=True),
            TurnEnded(),
            SessionClosed(reason="completed"),
        ]
    )
    # Arrange — the Gemini shape: every event carries the accumulated text
    gemini_shaped = _FakeInner(
        [
            AgentTranscript(text="Здрав", is_final=False),
            AgentTranscript(text="Здравствуйте", is_final=False),
            AgentTranscript(text="Здравствуйте", is_final=True),
            TurnEnded(),
            SessionClosed(reason="completed"),
        ]
    )

    # Act
    spoken: list[str] = []
    for inner in (openai_shaped, gemini_shaped):
        bridge = _bridge(inner)
        await bridge.connect(instructions="i", voice="", language="ru", params={})
        async for _event in bridge.events():
            pass
        await bridge.close()
        spoken.append("".join(_FakeTTS.instances[0].sent))

    # Assert
    assert spoken == ["Здравствуйте", "Здравствуйте"]


async def test_one_channel_is_opened_per_call_and_closed_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from assemblix_api.external.voice import speech_out as speech_out_module

    opened: list[Any] = []

    class _Channel:
        closed = False

        async def close(self) -> None:
            self.closed = True

    def fake_open_channel(_out: object) -> _Channel:
        channel = _Channel()
        opened.append(channel)
        return channel

    monkeypatch.setattr(speech_out_module, "open_channel", fake_open_channel)
    received: list[object] = []

    def open_stream(_out: object, *, on_audio: Any, on_error: Any, channel: object) -> _FakeTTS:
        received.append(channel)
        return _FakeTTS(on_audio, on_error)

    script: list[BridgeEvent] = [
        AgentTranscript(text="Раз.", is_final=False),
        AgentTranscript(text="Раз.", is_final=True),
        TurnEnded(),
        AgentTranscript(text="Два.", is_final=False),
        AgentTranscript(text="Два.", is_final=True),
        TurnEnded(),
        SessionClosed(reason="done"),
    ]
    bridge = HalfCascadeBridge(
        inner=_FakeInner(script),
        speech_out=_target(),
        output_sample_rate=16000,
        open_stream=open_stream,
    )

    await bridge.connect(instructions="", voice="", language="ru", params={})
    async for _event in bridge.events():
        pass
    await bridge.close()

    assert len(opened) == 1
    assert received == [opened[0], opened[0]]
    assert opened[0].closed is True


async def test_the_channel_is_closed_when_the_inner_connect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from assemblix_api.external.voice import speech_out as speech_out_module

    class _Channel:
        closes = 0

        async def close(self) -> None:
            self.closes += 1

    channel = _Channel()
    monkeypatch.setattr(speech_out_module, "open_channel", lambda _out: channel)

    class _FailingInner(_FakeInner):
        async def connect(self, **kwargs: Any) -> None:
            raise RuntimeError("connect failed")

    bridge = _bridge(_FailingInner([]))

    with pytest.raises(RuntimeError, match="connect failed"):
        await bridge.connect(instructions="", voice="", language="ru", params={})
    await bridge.close()

    assert channel.closes == 1


async def test_audio_from_an_aborted_session_is_not_forwarded() -> None:
    """A provider that keeps calling back after a barge-in aborted its session must
    not reach the caller, while the next turn's audio still does."""
    # Arrange
    inner = _FakeInner(
        [
            AgentTranscript(text="Длинный ", is_final=False),
            SpeechStarted(),
            TurnEnded(),
            AgentTranscript(text="Слушаю", is_final=False),
            AgentTranscript(text="Слушаю", is_final=True),
            TurnEnded(),
            SessionClosed(reason="closed"),
        ]
    )
    bridge = _bridge(inner)

    # Act
    await bridge.connect(instructions="i", voice="", language="ru", params={})
    seen: list[BridgeEvent] = []
    async for event in bridge.events():
        seen.append(event)
        if isinstance(event, SpeechStarted):
            await bridge.interrupt(audio_end_ms=100)
            await _FakeTTS.instances[0].on_audio(b"\xde\xad", None)
        if (
            isinstance(event, AgentTranscript)
            and not event.is_final
            and len(_FakeTTS.instances) == 2
        ):
            await _FakeTTS.instances[1].on_audio(b"\x01\x02", None)
    await bridge.close()

    # Assert
    assert _FakeTTS.instances[0].aborted is True
    audio = [e.pcm for e in seen if isinstance(e, AudioDelta)]
    assert audio == [b"\x01\x02"]


class _GatedInner(_FakeInner):
    """Scripted like _FakeInner, but an asyncio.Event in the script is awaited."""

    async def events(self) -> AsyncIterator[BridgeEvent]:
        for item in self._script:
            if isinstance(item, asyncio.Event):
                await item.wait()
                continue
            yield item
            await asyncio.sleep(0)


class _SlowFlushTTS(_FakeTTS):
    """Synthesis outlasts generation: the flush plays audio, then holds until released."""

    def __init__(self, on_audio: Any, on_error: Any, release: asyncio.Event) -> None:
        super().__init__(on_audio, on_error)
        self.release = release
        self.flush_done = False

    async def flush_and_close(self) -> int:
        await self.on_audio(b"\x01\x01", None)
        await self.release.wait()
        self.flush_done = True
        return sum(len(part) for part in self.sent)


def _slow_bridge(inner: _FakeInner, release: asyncio.Event) -> HalfCascadeBridge:
    _FakeTTS.instances.clear()
    return HalfCascadeBridge(
        inner=inner,
        speech_out=_target(),
        output_sample_rate=16000,
        open_stream=lambda _out, on_audio, on_error, **_kwargs: _SlowFlushTTS(
            on_audio, on_error, release
        ),
    )


async def test_a_barge_in_is_not_held_behind_the_previous_reply_still_synthesizing() -> None:
    """The model finished long ago and synthesis is still running: the caller's
    speech reaches the consumer at once, the synthesis is cut, and the finished
    turn is still reported — final transcript first, then TurnEnded."""
    # Arrange
    caller_speaks = asyncio.Event()
    inner = _GatedInner(
        [
            AgentTranscript(text="Добрый день", is_final=False),
            AgentTranscript(text="Добрый день", is_final=True),
            TurnEnded(output_tokens=5),
            caller_speaks,
            SpeechStarted(),
            SessionClosed(reason="closed"),
        ]
    )
    bridge = _slow_bridge(inner, release=asyncio.Event())

    # Act
    await bridge.connect(instructions="i", voice="", language="ru", params={})
    seen: list[BridgeEvent] = []
    flush_done_at_barge_in: bool | None = None
    async for event in bridge.events():
        seen.append(event)
        if isinstance(event, AudioDelta):
            caller_speaks.set()
        if isinstance(event, SpeechStarted):
            tts = _FakeTTS.instances[0]
            assert isinstance(tts, _SlowFlushTTS)
            flush_done_at_barge_in = tts.flush_done
            await tts.on_audio(b"\xde\xad", None)
    await bridge.close()

    # Assert
    assert flush_done_at_barge_in is False
    assert _FakeTTS.instances[0].aborted is True
    assert seen == [
        AgentTranscript(text="Добрый день", is_final=False),
        AudioDelta(pcm=b"\x01\x01"),
        SpeechStarted(),
        AgentTranscript(text="Добрый день", is_final=True),
        TurnEnded(output_tokens=5, speech_chars=len("Добрый день")),
        SessionClosed(reason="closed"),
    ]


async def test_without_a_barge_in_a_turn_ends_after_its_audio() -> None:
    # Arrange
    release = asyncio.Event()
    inner = _FakeInner(
        [
            AgentTranscript(text="Слушаю", is_final=False),
            AgentTranscript(text="Слушаю", is_final=True),
            TurnEnded(),
            SessionClosed(reason="closed"),
        ]
    )
    bridge = _slow_bridge(inner, release)

    # Act
    await bridge.connect(instructions="i", voice="", language="ru", params={})
    seen: list[BridgeEvent] = []
    async for event in bridge.events():
        seen.append(event)
        if isinstance(event, AudioDelta):
            release.set()
    await bridge.close()

    # Assert
    assert _FakeTTS.instances[0].aborted is False
    assert seen == [
        AgentTranscript(text="Слушаю", is_final=False),
        AudioDelta(pcm=b"\x01\x01"),
        AgentTranscript(text="Слушаю", is_final=True),
        TurnEnded(speech_chars=len("Слушаю")),
        SessionClosed(reason="closed"),
    ]


class _ScriptedTTS(_FakeTTS):
    """Speaks one second of 16 kHz audio when flushed."""

    async def flush_and_close(self) -> int:
        await self.on_audio(b"\x00\x00" * 16000, None)
        return await super().flush_and_close()


class _Browser:
    media = "ws"

    def __init__(self, turn_played: asyncio.Event) -> None:
        self._turn_played = turn_played

    async def send_json(self, data: dict) -> None: ...

    async def send_bytes(self, data: bytes) -> None: ...

    async def interrupt_playback(self) -> int | None:
        return None

    async def end_of_utterance(self) -> None:
        self._turn_played.set()

    async def __aiter__(self) -> AsyncIterator[Any]:
        await asyncio.Event().wait()
        yield b""


async def _call_with_a_late_barge_in(*, late: bool) -> list[int]:
    from assemblix_api.realtime.runtime import VoiceSessionRuntime

    now = [100.0]
    turn_played = asyncio.Event()

    class _Inner(_GatedInner):
        async def events(self) -> AsyncIterator[BridgeEvent]:
            yield AgentTranscript(text="Чем могу помочь?", is_final=True)
            yield TurnEnded()
            await turn_played.wait()
            now[0] += 0.25
            yield SpeechStarted()
            yield SessionClosed(reason="closed")

    inner = _Inner([])
    if late:
        inner.accepts_late_interrupt = True  # type: ignore[attr-defined]
    _FakeTTS.instances.clear()
    bridge = HalfCascadeBridge(
        inner=inner,
        speech_out=_target(),
        output_sample_rate=16000,
        open_stream=lambda _out, on_audio, on_error, **_kwargs: _ScriptedTTS(on_audio, on_error),
    )
    runtime = VoiceSessionRuntime(
        bridge=bridge,
        client=_Browser(turn_played),
        instructions="i",
        voice="",
        language="ru",
        params={},
        max_session_sec=5,
        clock=lambda: now[0],
    )

    await runtime.run()
    return inner.interrupts


async def test_a_late_barge_in_reaches_a_brain_that_can_truncate_its_reply() -> None:
    """End to end over the runtime: the reply was fully synthesized and the turn
    ended, a quarter of a second into playback the caller speaks — the brain is
    told what was heard so its history keeps only that."""
    # Act
    late_interrupts = await _call_with_a_late_barge_in(late=True)
    speech_to_speech_interrupts = await _call_with_a_late_barge_in(late=False)

    # Assert
    assert late_interrupts == [250]
    assert speech_to_speech_interrupts == []
