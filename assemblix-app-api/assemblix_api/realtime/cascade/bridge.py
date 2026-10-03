"""Cascade conversation bridge: streaming STT, local turn-taking, a text brain.

Implements ``RealtimeBridge`` so the runtime cannot tell it from a speech-to-speech
provider. It never produces audio: ``HalfCascadeBridge`` wraps it and speaks the
``AgentTranscript`` text emitted here.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import numpy as np
import structlog

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    BridgeError,
    BridgeEvent,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    TurnTimings,
    UserTranscript,
)
from assemblix_api.external.voice.stt_stream import SttStream, SttUnavailable
from assemblix_api.realtime.cascade.brain import Brain, BrainUsage, Turn
from assemblix_api.realtime.cascade.setup import CascadeMeter, CascadeSetup
from assemblix_api.realtime.cascade.turn import (
    EndOfTurn,
    PauseCancelled,
    PauseStart,
    SpeechStart,
    TurnDetector,
    TurnUpdate,
)

logger = structlog.get_logger(__name__)

# Pauses in one user turn that may start a speculative reply; later ones wait for EndOfTurn.
_MAX_SPECULATIONS_PER_TURN = 3
# Russian TTS speaks roughly 14 characters per second.
_CHARS_PER_SECOND = 14.0


def heard_prefix(text: str, audio_end_ms: int) -> str:
    limit = int(audio_end_ms / 1000 * _CHARS_PER_SECOND)
    if limit >= len(text):
        return text
    cut = text.rfind(" ", 0, limit + 1)
    return text[:cut] if cut > 0 else ""


class _BrainTimeout(Exception):
    pass


@dataclass
class _BrainCall:
    """One brain call in flight, kept so its debug record survives a cancellation."""

    messages: list[dict[str, str]]
    started: float
    stt_bytes: int = 0
    ttft_ms: int | None = None


@dataclass
class _TurnRun:
    """One user turn being answered. A speculative run starts at a tentative end of
    turn and stays held — nothing emitted, user turn uncommitted — until confirmed."""

    speculative: bool
    confirmed: asyncio.Event = field(default_factory=asyncio.Event)
    eou_ms: int = 0
    decided_at: float = 0.0
    smart_turn_prob: float | None = None
    smart_turn_asks: int = 0
    user_text: str = ""
    awaiting_final: bool = False
    stt_done_at: float | None = None
    brain_started_at: float | None = None
    first_token_at: float | None = None
    usage: BrainUsage | None = None
    released: bool = False

    def confirm(self, signal: EndOfTurn, at: float) -> None:
        self.eou_ms = signal.eou_ms
        self.decided_at = at
        self.smart_turn_prob = signal.smart_turn_prob
        self.smart_turn_asks = signal.smart_turn_asks
        self.confirmed.set()


async def _cancel_and_wait(task: asyncio.Future) -> None:
    """Cancel ``task`` and wait for it without absorbing a cancellation of the caller."""
    if not task.done():
        task.cancel()
        await asyncio.wait({task})
    if not task.cancelled():
        task.exception()


class CascadeBridge:
    input_sample_rate = 16000
    output_sample_rate = 16000
    # A reply finishes long before the caller has heard it; interrupt() after
    # TurnEnded still truncates it to what was heard.
    accepts_late_interrupt = True

    def __init__(
        self,
        *,
        stt: SttStream,
        detector: TurnDetector,
        brain: Brain,
        meter: CascadeMeter,
        clock: Callable[[], float] = time.monotonic,
        stt_final_timeout: float = 0.3,
        first_token_timeout: float = 5.0,
        stt_cost_per_minute: float = 0.0,
    ) -> None:
        self._stt = stt
        self._detector = detector
        self._brain = brain
        self._meter = meter
        self._clock = clock
        self._stt_final_timeout = stt_final_timeout
        self._first_token_timeout = first_token_timeout
        self._stt_cost_per_minute = stt_cost_per_minute
        self._queue: asyncio.Queue[BridgeEvent] = asyncio.Queue()
        self._history: list[Turn] = []
        self._pending_user: list[str] = []
        self._finals: list[str] = []
        self._partial = ""
        self._final_event = asyncio.Event()
        self._reply_task: asyncio.Task[None] | None = None
        self._reply_text = ""
        self._interrupted_index: int | None = None
        self._interrupted_text = ""
        self._barge_in_pending = False
        self._early_heard_ms: int | None = None
        self._stale_finals = 0
        # Finals of a speculative finalize whose run was discarded: kept as text, but
        # they must not answer a later finalize.
        self._orphan_finals = 0
        self._run: _TurnRun | None = None
        self._speculations = 0
        self._detector_lock = asyncio.Lock()
        self._settle_task: asyncio.Task[None] | None = None
        self._stt_pump: asyncio.Task[None] | None = None
        # Audio sent to STT: in the open utterance, and in finished ones not yet answered.
        self._stt_bytes = 0
        self._unanswered_stt_bytes = 0
        self._call: _BrainCall | None = None

    async def connect(
        self,
        *,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
        text_output: bool = False,
    ) -> None:
        opening = [
            asyncio.ensure_future(self._stt.open(language=language)),
            asyncio.ensure_future(self._brain.prepare(instructions=instructions)),
        ]
        try:
            await asyncio.gather(*opening)
        except BaseException:
            for task in opening:
                await _cancel_and_wait(task)
            with contextlib.suppress(Exception):
                await self._stt.close()
            raise
        self._stt_pump = asyncio.create_task(self._pump_stt())

    async def send_audio(self, pcm: bytes) -> None:
        async with self._detector_lock:
            pending = await self._apply(await self._detector.push(pcm))
        if pending is not None and (self._settle_task is None or self._settle_task.done()):
            self._settle_task = asyncio.create_task(self._settle(pending))

    async def _settle(self, pending: asyncio.Future[float] | None) -> None:
        """Wait out Smart Turn asks off the audio path, then process the audio behind them."""
        while pending is not None:
            await asyncio.wait({pending})
            async with self._detector_lock:
                pending = await self._apply(await self._detector.push(b""))

    async def _apply(self, update: TurnUpdate) -> asyncio.Future[float] | None:
        if update.stt_audio:
            self._stt_bytes += len(update.stt_audio)
            await self._stt.send_audio(update.stt_audio)
        for signal in update.signals:
            if isinstance(signal, SpeechStart):
                await self._on_speech_start()
            elif isinstance(signal, PauseStart):
                self._on_pause_start()
            elif isinstance(signal, PauseCancelled):
                await self._discard_speculation()
            elif isinstance(signal, EndOfTurn):
                self._on_end_of_turn(signal)
        return update.pending

    async def interrupt(self, *, audio_end_ms: int) -> None:
        if self._interrupted_index is None:
            if self._barge_in_pending:
                self._early_heard_ms = audio_end_ms
            return
        self._apply_heard(audio_end_ms)

    def _apply_heard(self, audio_end_ms: int) -> None:
        if self._interrupted_index is None:
            return
        self._history[self._interrupted_index] = Turn(
            "assistant", heard_prefix(self._interrupted_text, audio_end_ms)
        )
        self._interrupted_index = None

    async def events(self) -> AsyncIterator[BridgeEvent]:
        while True:
            event = await self._queue.get()
            yield event
            if isinstance(event, SessionClosed):
                return

    async def close(self) -> None:
        for task in (self._settle_task, self._reply_task, self._stt_pump):
            if task is not None:
                await _cancel_and_wait(task)
        self._detector.close()
        try:
            await self._stt.close()
        finally:
            self._meter.stt_seconds = self._stt.billed_seconds
            await self._queue.put(SessionClosed(reason="closed"))

    async def _on_speech_start(self) -> None:
        await self._discard_speculation()
        self._speculations = 0
        self._stale_finals = 0
        self._orphan_finals = 0
        await self._queue.put(SpeechStarted())
        task = self._reply_task
        if task is None or task.done():
            return
        self._barge_in_pending = True
        self._early_heard_ms = None
        await _cancel_and_wait(task)
        usage = self._run.usage if self._run is not None and self._run.usage else BrainUsage()
        self._meter.brain_cost_usd += usage.cost_usd
        if not self._reply_text:
            self._barge_in_pending = False
            self._close_call("", usage, outcome="cancelled")
            return
        # Barge-in: until interrupt() says how much was heard, none of it counts.
        self._history.append(Turn("assistant", ""))
        self._interrupted_index = len(self._history) - 1
        self._interrupted_text = self._reply_text
        self._barge_in_pending = False
        if self._early_heard_ms is not None:
            self._apply_heard(self._early_heard_ms)
            self._early_heard_ms = None
        record, turn_usage = self._close_call(self._reply_text, usage, outcome="cancelled")
        await self._queue.put(AgentTranscript(text=self._reply_text, is_final=True))
        await self._queue.put(TurnEnded(llm_call=record, usage=turn_usage))
        self._reply_text = ""

    def _on_pause_start(self) -> None:
        if self._speculations >= _MAX_SPECULATIONS_PER_TURN:
            return
        self._speculations += 1
        self._unanswered_stt_bytes += self._stt_bytes
        self._stt_bytes = 0
        run = _TurnRun(speculative=True)
        self._run = run
        self._reply_task = asyncio.create_task(self._finish_turn(run))

    async def _discard_speculation(self) -> None:
        """Speech resumed before the end of turn was confirmed: drop the held reply
        unseen. The heard text stays pending and merges into what follows."""
        run = self._run
        if run is None or run.confirmed.is_set():
            return
        self._run = None
        if self._reply_task is not None:
            await _cancel_and_wait(self._reply_task)
        if run.awaiting_final and not self._final_event.is_set():
            self._orphan_finals += 1
        if self._call is not None:
            usage = run.usage
            # Cancelled mid-stream the provider never reports usage, so price it from text.
            if usage is None:
                usage = self._brain.estimate_usage(self._call.messages, self._reply_text)
            self._meter.brain_cost_usd += usage.cost_usd
            self._close_call(
                self._reply_text,
                usage,
                outcome="speculative_discarded",
                estimated=run.usage is None,
            )
        self._reply_text = ""

    def _on_end_of_turn(self, signal: EndOfTurn) -> None:
        self._unanswered_stt_bytes += self._stt_bytes
        self._stt_bytes = 0
        self._interrupted_index = None
        now = self._clock()
        run = self._run
        if run is not None and not run.confirmed.is_set():
            run.confirm(signal, now)
            if run.first_token_at is not None:
                self._release(run)
            return
        run = _TurnRun(speculative=False)
        run.confirm(signal, now)
        self._run = run
        self._reply_task = asyncio.create_task(self._finish_turn(run))

    async def _finish_turn(self, run: _TurnRun) -> None:
        self._final_event.clear()
        run.awaiting_final = True
        try:
            await self._stt.finalize()
            await asyncio.wait_for(self._final_event.wait(), self._stt_final_timeout)
        except TimeoutError:
            self._stale_finals += 1
        except Exception as exc:  # noqa: BLE001 — continue with the partial text.
            logger.warning("voice.cascade.stt_finalize_failed", error=str(exc))
        run.awaiting_final = False
        run.stt_done_at = self._clock()
        heard = " ".join(filter(None, [*self._finals, self._partial.strip()])).strip()
        self._finals.clear()
        self._partial = ""
        if heard:
            self._pending_user.append(heard)
        run.user_text = " ".join(self._pending_user).strip()
        if not run.user_text:
            return
        await self._reply(run)

    async def _reply(self, run: _TurnRun) -> None:
        user_text = run.user_text
        started = self._clock()
        run.brain_started_at = started
        first_token = asyncio.Event()
        history = list(self._history)
        call = _BrainCall(messages=self._brain.conversation(history, user_text), started=started)
        self._call = call

        async def on_delta(text: str) -> None:
            if not text:
                return
            if not first_token.is_set():
                first_token.set()
                run.first_token_at = self._clock()
                call.ttft_ms = int((run.first_token_at - started) * 1000)
            self._reply_text += text
            if run.released:
                await self._queue.put(AgentTranscript(text=self._reply_text, is_final=False))
            elif run.confirmed.is_set():
                self._release(run)

        reply = asyncio.create_task(
            self._brain.reply(history=history, user_text=user_text, on_delta=on_delta)
        )
        try:
            usage = await self._await_reply(reply, first_token)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — a failed reply must not end the call.
            code = "brain_timeout" if isinstance(exc, _BrainTimeout) else "brain_failed"
            logger.warning("voice.cascade.brain_failed", code=code, error=str(exc))
            await run.confirmed.wait()
            self._release(run)
            await self._finish_reply(BrainUsage(), outcome=code, error=str(exc))
            await self._queue.put(BridgeError(code=code, message=str(exc), is_fatal=False))
            return
        finally:
            if not reply.done():
                reply.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await reply
        run.usage = usage
        await run.confirmed.wait()
        self._release(run)
        await self._finish_reply(usage)

    def _release(self, run: _TurnRun) -> None:
        """Commit the user turn and, once there is reply text, its timings and text so far.

        Stage timings count from the confirmed end of turn, so with a speculative run
        ``stt_final_ms`` and ``brain_first_token_ms`` are only the residual waits after
        confirmation (0 when already done) and eou + stt + llm + tts still adds up to
        the total; ``llm_overlap_ms`` is the LLM time hidden inside the pause.
        """
        if run.released:
            return
        run.released = True
        self._commit_user(run.user_text)
        if run.first_token_at is None or run.stt_done_at is None:
            return
        brain_started = run.brain_started_at or run.stt_done_at
        stt_wait = max(0.0, run.stt_done_at - run.decided_at)
        brain_wait = max(0.0, run.first_token_at - max(run.decided_at, brain_started))
        overlap = max(0.0, min(run.decided_at, run.first_token_at) - brain_started)
        self._queue.put_nowait(
            TurnTimings(
                speech_ended_at=run.decided_at - run.eou_ms / 1000,
                eou_ms=run.eou_ms,
                stt_final_ms=int(stt_wait * 1000),
                brain_first_token_ms=int(brain_wait * 1000),
                smart_turn_prob=run.smart_turn_prob,
                smart_turn_asks=run.smart_turn_asks,
                speculative=run.speculative,
                llm_overlap_ms=int(overlap * 1000),
            )
        )
        if self._reply_text:
            self._queue.put_nowait(AgentTranscript(text=self._reply_text, is_final=False))

    async def _await_reply(
        self, reply: asyncio.Task[BrainUsage], first_token: asyncio.Event
    ) -> BrainUsage:
        waiter = asyncio.create_task(first_token.wait())
        try:
            await asyncio.wait(
                {reply, waiter},
                timeout=self._first_token_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            waiter.cancel()
        if not first_token.is_set() and not reply.done():
            raise _BrainTimeout(f"No reply text within {self._first_token_timeout:.0f} s")
        return await reply

    def _commit_user(self, user_text: str) -> None:
        if self._call is not None:
            self._call.stt_bytes = self._unanswered_stt_bytes
        self._unanswered_stt_bytes = 0
        self._pending_user.clear()
        self._history.append(Turn("user", user_text))
        self._queue.put_nowait(UserTranscript(text=user_text, is_final=True))

    async def _finish_reply(
        self, usage: BrainUsage, *, outcome: str = "ok", error: str | None = None
    ) -> None:
        text, self._reply_text = self._reply_text, ""
        self._meter.brain_cost_usd += usage.cost_usd
        record, turn_usage = self._close_call(text, usage, outcome=outcome, error=error)
        if text:
            self._history.append(Turn("assistant", text))
            self._interrupted_index = len(self._history) - 1
            self._interrupted_text = text
            await self._queue.put(AgentTranscript(text=text, is_final=True))
        await self._queue.put(
            TurnEnded(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                llm_call=record,
                usage=turn_usage,
            )
        )

    def _close_call(
        self,
        text: str,
        usage: BrainUsage,
        *,
        outcome: str,
        error: str | None = None,
        estimated: bool = False,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Turn the call in flight into its debug record and per-turn spend, and log it."""
        call, self._call = self._call, None
        if call is None:
            return None, None
        info = self._brain.describe()
        duration_ms = int((self._clock() - call.started) * 1000)
        cost_usd = float(usage.cost_usd)
        record: dict[str, Any] = {
            "provider": info.get("provider"),
            "model": info.get("model"),
            "effectiveModel": usage.effective_model,
            "params": info.get("params") or {},
            "messages": call.messages,
            "response": text,
            "inputTokens": usage.input_tokens,
            "outputTokens": usage.output_tokens,
            "cachedInputTokens": usage.cached_input_tokens,
            "costUsd": cost_usd,
            "ttftMs": call.ttft_ms,
            "durationMs": duration_ms,
            "outcome": outcome,
            "error": error,
        }
        if estimated:
            record["estimated"] = True
        stt_seconds = call.stt_bytes / (2 * self.input_sample_rate)
        stt_cost = Decimal(str(stt_seconds)) / Decimal(60) * Decimal(str(self._stt_cost_per_minute))
        turn_usage: dict[str, Any] = {
            "sttSeconds": round(stt_seconds, 3),
            "sttCostUsdEstimate": float(stt_cost),
            "llmCostUsd": cost_usd,
        }
        logger.info(
            "voice.cascade.brain_call",
            provider=record["provider"],
            model=record["model"],
            effective_model=usage.effective_model,
            params=record["params"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            cost_usd=cost_usd,
            ttft_ms=call.ttft_ms,
            duration_ms=duration_ms,
            outcome=outcome,
        )
        return record, turn_usage

    async def _pump_stt(self) -> None:
        try:
            async for result in self._stt.results():
                if result.is_final:
                    # A final supersedes the phrase's partial, stale or not.
                    self._partial = ""
                    if self._stale_finals:
                        self._stale_finals -= 1
                        continue
                    if result.text.strip():
                        self._finals.append(result.text.strip())
                    if self._orphan_finals:
                        self._orphan_finals -= 1
                    else:
                        self._final_event.set()
                    continue
                self._partial = result.text
                preview = " ".join([*self._pending_user, *self._finals, result.text]).strip()
                if preview:
                    await self._queue.put(UserTranscript(text=preview, is_final=False))
        except SttUnavailable as exc:
            await self._queue.put(
                BridgeError(code="stt_unavailable", message=str(exc), is_fatal=True)
            )
        except Exception as exc:  # noqa: BLE001 — a dead pump must end the call loudly.
            await self._queue.put(BridgeError(code="stt_failed", message=str(exc), is_fatal=True))


def build_cascade_bridge(setup: CascadeSetup, meter: CascadeMeter) -> CascadeBridge:
    from assemblix_api.external.voice.stt_stream.yandex import YandexSttStream
    from assemblix_api.realtime.cascade.brain import PromptBrain
    from assemblix_api.realtime.cascade.models import load_turn_models

    models = load_turn_models()
    smart_turn = models.smart_turn

    async def completion(audio: np.ndarray) -> float:
        return await asyncio.to_thread(smart_turn.completion_probability, audio)

    return CascadeBridge(
        stt=YandexSttStream(credential=setup.stt_api_key, model=setup.stt_model),
        detector=TurnDetector(vad=models.new_vad(), completion=completion, config=setup.turn),
        brain=PromptBrain(
            provider=setup.brain_provider,
            model=setup.brain_model,
            api_key=setup.brain_api_key,
            params=setup.brain_params,
            history_turns=setup.history_turns,
        ),
        meter=meter,
        stt_cost_per_minute=setup.stt_cost_per_minute,
    )
