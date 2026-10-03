import asyncio
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Any

import pytest

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    BridgeError,
    SpeechStarted,
    TurnEnded,
    TurnTimings,
    UserTranscript,
)
from assemblix_api.external.voice.stt_stream import SttResult, SttUnavailable
from assemblix_api.realtime.cascade.brain import BrainUsage, OnDelta, PromptBrain, Turn
from assemblix_api.realtime.cascade.bridge import CascadeBridge, heard_prefix
from assemblix_api.realtime.cascade.setup import CascadeMeter
from assemblix_api.realtime.cascade.turn import EndOfTurn, SpeechStart, TurnUpdate
from assemblix_api.schemas.execution import AgentExecutionResult


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

    def describe(self) -> dict[str, Any]:
        return {"provider": "fake", "model": "fake-1", "params": {}}

    def conversation(self, history: Sequence[Turn], user_text: str) -> list[dict[str, str]]:
        turns = [{"role": t.role, "content": t.text} for t in history if t.text]
        return [*turns, {"role": "user", "content": user_text}]

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
    assert isinstance(seen[6], TurnEnded)
    assert (seen[6].input_tokens, seen[6].output_tokens) == (10, 2)
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


async def test_late_stt_final_does_not_leak_into_the_next_turn() -> None:
    class _LateStt(_Stt):
        async def finalize(self) -> None:
            self.finalized += 1
            if self.finalized == 1:
                asyncio.get_running_loop().call_later(
                    0.3, self.queue.put_nowait, SttResult("мне нужно", True)
                )
            else:
                self.queue.put_nowait(SttResult("дальше", True))

    stt = _LateStt()
    brain = _Brain(["Ок"])
    bridge, _, _, _ = await _bridge(brain, stt)
    stt.queue.put_nowait(SttResult("мне", False))

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await asyncio.sleep(0.5)
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    assert [call[1] for call in brain.calls] == ["мне", "дальше"]
    await bridge.close()


async def test_interrupt_during_barge_in_teardown_is_not_lost() -> None:
    gate = asyncio.Event()
    release = asyncio.Event()
    long_reply = "Конечно, у нас есть несколько вариантов от кашля, давайте я расскажу подробнее"

    class _SlowTeardownBrain(_Brain):
        async def reply(
            self, *, history: Sequence[Turn], user_text: str, on_delta: OnDelta
        ) -> BrainUsage:
            self.calls.append((list(history), user_text))
            await on_delta(long_reply)
            try:
                await gate.wait()
            finally:
                await release.wait()
            return BrainUsage()

    brain = _SlowTeardownBrain([])
    bridge, stt, _, _ = await _bridge(brain)
    stt.finals = ["есть сироп?", "стоп"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()
    barge = asyncio.create_task(bridge.send_audio(b"S"))
    await asyncio.sleep(0.05)
    await bridge.interrupt(audio_end_ms=1000)
    release.set()
    await barge
    await bridge.send_audio(b"E")
    await _settle()

    heard = brain.calls[-1][0][1].text
    assert long_reply.startswith(heard) and 0 < len(heard) < len(long_reply)
    await bridge.close()


async def test_interrupt_after_the_brain_finished_truncates_history() -> None:
    long_reply = "Конечно, у нас есть несколько вариантов от кашля, давайте я расскажу подробнее"
    brain = _Brain([long_reply])
    bridge, stt, _, _ = await _bridge(brain)
    stt.finals = ["есть сироп?", "стоп"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()
    await bridge.interrupt(audio_end_ms=1000)
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    heard = brain.calls[-1][0][1].text
    assert long_reply.startswith(heard) and 0 < len(heard) < len(long_reply)
    await bridge.close()


async def test_empty_delta_does_not_commit_the_user_turn() -> None:
    brain = _Brain(["", "Привет"])
    bridge, stt, _, seen = await _bridge(brain)
    stt.finals = ["алло"]

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    assert [type(e).__name__ for e in seen][:3] == [
        "SpeechStarted",
        "UserTranscript",
        "TurnTimings",
    ]
    assert AgentTranscript(text="Привет", is_final=False) in seen
    assert AgentTranscript(text="", is_final=False) not in seen
    await bridge.close()


async def test_stt_unexpected_error_is_fatal_and_close_still_finishes() -> None:
    class _FailingClose(_Stt):
        async def close(self) -> None:
            raise RuntimeError("close failed")

    stt = _FailingClose()
    bridge, _, meter, seen = await _bridge(_Brain([]), stt)
    stt.queue.put_nowait(RuntimeError("boom"))
    await _settle()

    assert any(isinstance(e, BridgeError) and e.code == "stt_failed" and e.is_fatal for e in seen)
    try:
        await bridge.close()
    except RuntimeError:
        pass
    assert meter.stt_seconds == 30.0
    await _settle()
    assert type(seen[-1]).__name__ == "SessionClosed"


async def test_finalize_failure_falls_back_to_the_partial() -> None:
    class _BadFinalize(_Stt):
        async def finalize(self) -> None:
            raise RuntimeError("stream gone")

    stt = _BadFinalize()
    brain = _Brain(["Ок"])
    bridge, _, _, _ = await _bridge(brain, stt)
    stt.queue.put_nowait(SttResult("алло", False))

    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    assert brain.calls[-1][1] == "алло"
    await bridge.close()


async def test_a_failed_connect_closes_the_stt_stream() -> None:
    class _ClosingStt(_Stt):
        closed = False

        async def close(self) -> None:
            self.closed = True

    class _BrokenBrain(_Brain):
        async def prepare(self, *, instructions: str) -> None:
            raise RuntimeError("no prompt")

    stt = _ClosingStt()
    bridge = CascadeBridge(
        stt=stt, detector=_Detector(), brain=_BrokenBrain([]), meter=CascadeMeter()
    )

    with pytest.raises(RuntimeError, match="no prompt"):
        await bridge.connect(instructions="Роль.", voice="", language="ru", params={})

    assert stt.closed is True


async def test_a_barge_in_does_not_swallow_a_cancellation_of_the_caller() -> None:
    class _StubbornBrain(_Brain):
        async def reply(self, **_kw: Any) -> BrainUsage:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await asyncio.sleep(0.05)
                raise
            return BrainUsage()

    bridge, stt, _, _ = await _bridge(_StubbornBrain([]))
    stt.finals = ["вопрос"]
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    barge_in = asyncio.create_task(bridge.send_audio(b"S"))
    await asyncio.sleep(0.01)
    barge_in.cancel()

    with pytest.raises(asyncio.CancelledError):
        await barge_in
    await bridge.close()


class _Runner:
    """AgentRunner stand-in: streams one scripted reply per call and records the call."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> AgentExecutionResult:
        self.calls.append(kwargs)
        reply = self.replies[len(self.calls) - 1]
        await kwargs["on_delta"](reply)
        return AgentExecutionResult(
            content=reply,
            parsed_content=None,
            metadata={
                "input_tokens": 120,
                "output_tokens": 6,
                "cached_input_tokens": 64,
                "cost": 0.0002,
                "effective_model": "gpt-4.1-mini-2025",
            },
            messages=[],
            tool_executions=[],
        )


def _turn_ends(seen: list[Any]) -> list[TurnEnded]:
    return [e for e in seen if isinstance(e, TurnEnded)]


async def test_a_turn_records_the_exact_llm_call_with_heard_truncation() -> None:
    """The record holds the messages the runner actually got — history window plus the
    current message, the interrupted reply cut to what was heard — and the call's
    params, usage, timing and per-turn STT spend."""
    # Arrange
    long_reply = "Конечно, у нас есть несколько вариантов от кашля, давайте я расскажу подробнее"
    runner = _Runner([long_reply, "Хорошо."])
    brain = PromptBrain(
        provider="openai",
        model="gpt-4.1-mini",
        api_key="k",
        params={"max_completion_tokens": 200},
        history_turns=1,
        runner=runner,
        build_model=lambda *a, **kw: "MODEL",
    )
    stt = _Stt()
    meter = CascadeMeter()
    bridge = CascadeBridge(
        stt=stt,
        detector=_Detector(),
        brain=brain,
        meter=meter,
        stt_final_timeout=0.2,
        stt_cost_per_minute=0.6,
    )
    await bridge.connect(instructions="Роль.", voice="", language="ru", params={})
    seen: list[Any] = []

    async def consume() -> None:
        async for event in bridge.events():
            seen.append(event)

    asyncio.get_running_loop().create_task(consume())
    stt.finals = ["есть сироп?", "стоп"]
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()
    await bridge.interrupt(audio_end_ms=1000)

    # Act
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    # Assert
    record = _turn_ends(seen)[-1].llm_call
    assert record is not None
    assert record["messages"] == runner.calls[-1]["conversation"]
    assert record["messages"][0] == {"role": "assistant", "content": "Конечно, у нас"}
    assert record["messages"][-1] == {"role": "user", "content": "стоп"}
    assert len(record["messages"]) == 2  # history_turns=1 plus the current message
    assert record["provider"] == "openai" and record["model"] == "gpt-4.1-mini"
    assert record["effectiveModel"] == "gpt-4.1-mini-2025"
    assert record["params"] == {"max_completion_tokens": 200}
    assert record["response"] == "Хорошо."
    assert (record["inputTokens"], record["outputTokens"], record["cachedInputTokens"]) == (
        120,
        6,
        64,
    )
    assert record["costUsd"] == 0.0002
    assert isinstance(record["ttftMs"], int) and record["ttftMs"] >= 0
    assert record["durationMs"] >= record["ttftMs"]
    assert record["outcome"] == "ok" and record["error"] is None
    usage = _turn_ends(seen)[-1].usage
    assert usage == {
        "sttSeconds": round(10 / 32000, 3),
        "sttCostUsdEstimate": float(Decimal(str(10 / 32000)) / Decimal(60) * Decimal("0.6")),
        "llmCostUsd": 0.0002,
    }
    await bridge.close()


async def test_a_barge_in_records_the_call_as_cancelled() -> None:
    # Arrange
    gate = asyncio.Event()
    brain = _Brain(["Конечно, давайте", " подробнее"], gate=gate)
    bridge, stt, _, seen = await _bridge(brain)
    stt.finals = ["есть сироп?"]
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    # Act
    await bridge.send_audio(b"S")
    await _settle()

    # Assert
    [ended] = _turn_ends(seen)
    assert ended.llm_call is not None
    assert ended.llm_call["outcome"] == "cancelled"
    assert ended.llm_call["response"] == "Конечно, давайте"
    assert ended.llm_call["messages"] == [{"role": "user", "content": "есть сироп?"}]
    await bridge.close()


async def test_a_brain_failure_records_the_outcome_and_error() -> None:
    # Arrange
    class _BrokenBrain(_Brain):
        async def reply(self, **_kw: Any) -> BrainUsage:
            raise RuntimeError("provider down")

    bridge, stt, _, seen = await _bridge(_BrokenBrain([]))
    stt.finals = ["алло"]

    # Act
    await bridge.send_audio(b"S")
    await bridge.send_audio(b"E")
    await _settle()

    # Assert
    [ended] = _turn_ends(seen)
    assert ended.llm_call is not None
    assert ended.llm_call["outcome"] == "brain_failed"
    assert ended.llm_call["error"] == "provider down"
    assert ended.llm_call["ttftMs"] is None
    assert ended.llm_call["messages"] == [{"role": "user", "content": "алло"}]
    await bridge.close()
