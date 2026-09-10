"""Half-cascade bridge: the model writes, a TTS provider speaks."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

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
        open_stream=lambda _out, on_audio, on_error: _FakeTTS(on_audio, on_error),
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
