import asyncio
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Any

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    BridgeError,
    SpeechStarted,
    TurnEnded,
    TurnTimings,
    UserTranscript,
)
from assemblix_api.external.voice.stt_stream import SttResult, SttUnavailable
from assemblix_api.realtime.cascade.brain import BrainUsage, OnDelta, Turn
from assemblix_api.realtime.cascade.bridge import CascadeBridge, heard_prefix
from assemblix_api.realtime.cascade.setup import CascadeMeter
from assemblix_api.realtime.cascade.turn import EndOfTurn, SpeechStart, TurnUpdate


class _Stt:
    def __init__(self) -> None:
        self.audio: list[bytes] = []
        self.finalized = 0
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.finals: list[str] = []
        self.billed_seconds = 30.0

    async def open(self, *, language: str) -> None: ...

    async def send_audio(self, pcm: bytes) -> None:
        self.audio.append(pcm)

    async def finalize(self) -> None:
        self.finalized += 1
        text = self.finals.pop(0) if self.finals else ""
        self.queue.put_nowait(SttResult(text, True))

    async def results(self) -> AsyncIterator[SttResult]:
        while True:
            item = await self.queue.get()
            if isinstance(item, Exception):
                raise item
            yield item

    async def close(self) -> None: ...


class _Detector:
    """Each pushed chunk is a script key: b"S" start, b"E" end of turn, else plain audio."""

    async def push(self, pcm: bytes) -> TurnUpdate:
        if pcm == b"S":
            return TurnUpdate(stt_audio=b"speech", signals=[SpeechStart()])
        if pcm == b"E":
            return TurnUpdate(stt_audio=b"tail", signals=[EndOfTurn(eou_ms=224)])
        return TurnUpdate(stt_audio=pcm)


class _Brain:
    def __init__(self, deltas: list[str], gate: asyncio.Event | None = None) -> None:
        self.deltas = deltas
        self.gate = gate
        self.calls: list[tuple[list[Turn], str]] = []
        self.instructions = ""

    async def prepare(self, *, instructions: str) -> None:
        self.instructions = instructions

    async def reply(
        self, *, history: Sequence[Turn], user_text: str, on_delta: OnDelta
    ) -> BrainUsage:
        self.calls.append((list(history), user_text))
        for index, delta in enumerate(self.deltas):
            await on_delta(delta)
            if index == 0 and self.gate is not None:
                await self.gate.wait()
        return BrainUsage(input_tokens=10, output_tokens=2, cost_usd=Decimal("0.001"))


async def _bridge(
    brain: _Brain, stt: _Stt | None = None
) -> tuple[CascadeBridge, _Stt, CascadeMeter, list[Any]]:
    stt = stt or _Stt()
    meter = CascadeMeter()
    bridge = CascadeBridge(
        stt=stt, detector=_Detector(), brain=brain, meter=meter, stt_final_timeout=0.2
    )
    await bridge.connect(instructions="Роль.", voice="", language="ru", params={})
    seen: list[Any] = []

    async def consume() -> None:
        async for event in bridge.events():
            seen.append(event)

    asyncio.get_running_loop().create_task(consume())
    return bridge, stt, meter, seen


async def _settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0.01)


async def test_full_turn_emits_user_text_timings_reply_and_usage() -> None:
    brain = _Brain(["Здравствуйте", "!"])
    bridge, stt, meter, seen = await _bridge(brain)
    stt.finals = ["добрый день"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    kinds = [type(e).__name__ for e in seen]
    assert kinds == [
        "SpeechStarted",
        "UserTranscript",
        "TurnTimings",
        "AgentTranscript",
        "AgentTranscript",
        "AgentTranscript",
        "TurnEnded",
    ]
    assert seen[1] == UserTranscript(text="добрый день", is_final=True)
    assert isinstance(seen[2], TurnTimings) and seen[2].eou_ms == 224
    assert seen[4] == AgentTranscript(text="Здравствуйте!", is_final=False)
    assert seen[5] == AgentTranscript(text="Здравствуйте!", is_final=True)
    assert seen[6] == TurnEnded(input_tokens=10, output_tokens=2)
    assert stt.audio == [b"speech", b"tail"] and stt.finalized == 1
    assert meter.brain_cost_usd == Decimal("0.001")
    assert brain.instructions == "Роль."
    await bridge.close()
    assert meter.stt_seconds == 30.0


async def test_noise_without_words_starts_no_reply() -> None:
    brain = _Brain(["x"])
    bridge, stt, _, seen = await _bridge(brain)
    stt.finals = [""]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    assert brain.calls == []
    assert [type(e).__name__ for e in seen] == ["SpeechStarted"]
    await bridge.close()


async def test_false_end_of_turn_merges_text_into_the_next_turn() -> None:
    gate = asyncio.Event()

    class _SlowBrain(_Brain):
        async def reply(
            self, *, history: Sequence[Turn], user_text: str, on_delta: OnDelta
        ) -> BrainUsage:
            self.calls.append((list(history), user_text))
            if len(self.calls) == 1:
                await gate.wait()  # cancelled before any delta
            await on_delta("Понял.")
            return BrainUsage()

    brain = _SlowBrain([])
    bridge, stt, _, seen = await _bridge(brain)
    stt.finals = ["мне нужно", "лекарство от кашля"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    assert brain.calls[-1][1] == "мне нужно лекарство от кашля"
    finals = [e for e in seen if isinstance(e, UserTranscript) and e.is_final]
    assert finals == [UserTranscript(text="мне нужно лекарство от кашля", is_final=True)]
    await bridge.close()


async def test_barge_in_after_text_cancels_and_keeps_only_what_was_heard() -> None:
    gate = asyncio.Event()
    long_reply = "Конечно, у нас есть несколько вариантов от кашля, давайте я расскажу подробнее"
    brain = _Brain([long_reply, " и ещё"], gate=gate)
    bridge, stt, _, seen = await _bridge(brain)
    stt.finals = ["есть сироп?", "стоп"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()
    await bridge.send_audio(b"S")  # caller talks over the agent
    await _settle()
    await bridge.interrupt(audio_end_ms=1000)  # runtime: 1 s of the reply was heard
    await bridge.send_audio(b"E")
    await _settle()

    assert seen.count(SpeechStarted()) == 2
    assert AgentTranscript(text=long_reply, is_final=True) in seen
    history = brain.calls[-1][0]
    assert history[0] == Turn("user", "есть сироп?")
    assert history[1].role == "assistant"
    assert long_reply.startswith(history[1].text) and 0 < len(history[1].text) < len(long_reply)
    assert brain.calls[-1][1] == "стоп"
    await bridge.close()


async def test_barge_in_before_any_audio_records_nothing_heard() -> None:
    gate = asyncio.Event()
    brain = _Brain(["Ответ", " длинный"], gate=gate)
    bridge, stt, _, _ = await _bridge(brain)
    stt.finals = ["вопрос", "ещё"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()
    await bridge.send_audio(b"S")  # no interrupt() follows: nothing was played
    await bridge.send_audio(b"E")
    await _settle()

    history = brain.calls[-1][0]
    assert [t.text for t in history if t.role == "assistant"] == [""]
    await bridge.close()


async def test_brain_failure_is_not_fatal() -> None:
    class _BrokenBrain(_Brain):
        async def reply(self, **_kw: Any) -> BrainUsage:
            raise RuntimeError("provider down")

    bridge, stt, _, seen = await _bridge(_BrokenBrain([]))
    stt.finals = ["алло"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    errors = [e for e in seen if isinstance(e, BridgeError)]
    assert errors and errors[0].code == "brain_failed" and errors[0].is_fatal is False
    assert UserTranscript(text="алло", is_final=True) in seen
    await bridge.close()


async def test_stt_outage_is_fatal() -> None:
    stt = _Stt()
    bridge, _, _, seen = await _bridge(_Brain([]), stt)

    stt.queue.put_nowait(SttUnavailable("down"))
    await _settle()

    assert any(
        isinstance(e, BridgeError) and e.code == "stt_unavailable" and e.is_fatal for e in seen
    )
    await bridge.close()


def test_heard_prefix_cuts_on_a_word_boundary() -> None:
    text = "Конечно, у нас есть несколько вариантов"

    assert heard_prefix(text, 0) == ""
    assert heard_prefix(text, 1000) == "Конечно, у нас"  # 14 chars/s, cut at a space
    assert heard_prefix(text, 600) == "Конечно,"
    assert heard_prefix(text, 400) == ""  # not even the first word was heard
    assert heard_prefix(text, 60_000) == text
