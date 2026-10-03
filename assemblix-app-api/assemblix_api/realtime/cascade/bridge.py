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
from assemblix_api.realtime.cascade.turn import EndOfTurn, SpeechStart, TurnDetector

logger = structlog.get_logger(__name__)

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
    ) -> None:
        self._stt = stt
        self._detector = detector
        self._brain = brain
        self._meter = meter
        self._clock = clock
        self._stt_final_timeout = stt_final_timeout
        self._first_token_timeout = first_token_timeout
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
        self._stt_pump: asyncio.Task[None] | None = None

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
        update = await self._detector.push(pcm)
        if update.stt_audio:
            await self._stt.send_audio(update.stt_audio)
        for signal in update.signals:
            if isinstance(signal, SpeechStart):
                await self._on_speech_start()
            elif isinstance(signal, EndOfTurn):
                self._on_end_of_turn(signal.eou_ms)

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
        for task in (self._reply_task, self._stt_pump):
            if task is not None:
                await _cancel_and_wait(task)
        try:
            await self._stt.close()
        finally:
            self._meter.stt_seconds = self._stt.billed_seconds
            await self._queue.put(SessionClosed(reason="closed"))

    async def _on_speech_start(self) -> None:
        self._stale_finals = 0
        await self._queue.put(SpeechStarted())
        task = self._reply_task
        if task is None or task.done():
            return
        self._barge_in_pending = True
        self._early_heard_ms = None
        await _cancel_and_wait(task)
        if not self._reply_text:
            self._barge_in_pending = False
            return
        # Barge-in: until interrupt() says how much was heard, none of it counts.
        self._history.append(Turn("assistant", ""))
        self._interrupted_index = len(self._history) - 1
        self._interrupted_text = self._reply_text
        self._barge_in_pending = False
        if self._early_heard_ms is not None:
            self._apply_heard(self._early_heard_ms)
            self._early_heard_ms = None
        await self._queue.put(AgentTranscript(text=self._reply_text, is_final=True))
        await self._queue.put(TurnEnded())
        self._reply_text = ""

    def _on_end_of_turn(self, eou_ms: int) -> None:
        self._interrupted_index = None
        self._reply_task = asyncio.create_task(self._finish_turn(eou_ms, self._clock()))

    async def _finish_turn(self, eou_ms: int, decided_at: float) -> None:
        self._final_event.clear()
        try:
            await self._stt.finalize()
            await asyncio.wait_for(self._final_event.wait(), self._stt_final_timeout)
        except TimeoutError:
            self._stale_finals += 1
        except Exception as exc:  # noqa: BLE001 — continue with the partial text.
            logger.warning("voice.cascade.stt_finalize_failed", error=str(exc))
        stt_final_ms = int((self._clock() - decided_at) * 1000)
        heard = (" ".join(self._finals) or self._partial).strip()
        self._finals.clear()
        self._partial = ""
        if heard:
            self._pending_user.append(heard)
        user_text = " ".join(self._pending_user).strip()
        if not user_text:
            return
        await self._reply(
            user_text,
            speech_ended_at=decided_at - eou_ms / 1000,
            eou_ms=eou_ms,
            stt_final_ms=stt_final_ms,
        )

    async def _reply(
        self, user_text: str, *, speech_ended_at: float, eou_ms: int, stt_final_ms: int
    ) -> None:
        started = self._clock()
        first_token = asyncio.Event()

        async def on_delta(text: str) -> None:
            if not text:
                return
            if not first_token.is_set():
                first_token.set()
                await self._commit_user(user_text)
                await self._queue.put(
                    TurnTimings(
                        speech_ended_at=speech_ended_at,
                        eou_ms=eou_ms,
                        stt_final_ms=stt_final_ms,
                        brain_first_token_ms=int((self._clock() - started) * 1000),
                    )
                )
            self._reply_text += text
            await self._queue.put(AgentTranscript(text=self._reply_text, is_final=False))

        history = list(self._history)
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
            if not first_token.is_set():
                await self._commit_user(user_text)
            await self._finish_reply(BrainUsage())
            await self._queue.put(BridgeError(code=code, message=str(exc), is_fatal=False))
            return
        finally:
            if not reply.done():
                reply.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await reply
        if not first_token.is_set():
            await self._commit_user(user_text)
        await self._finish_reply(usage)

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

    async def _commit_user(self, user_text: str) -> None:
        self._pending_user.clear()
        self._history.append(Turn("user", user_text))
        await self._queue.put(UserTranscript(text=user_text, is_final=True))

    async def _finish_reply(self, usage: BrainUsage) -> None:
        text, self._reply_text = self._reply_text, ""
        self._meter.brain_cost_usd += usage.cost_usd
        if text:
            self._history.append(Turn("assistant", text))
            self._interrupted_index = len(self._history) - 1
            self._interrupted_text = text
            await self._queue.put(AgentTranscript(text=text, is_final=True))
        await self._queue.put(
            TurnEnded(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
        )

    async def _pump_stt(self) -> None:
        try:
            async for result in self._stt.results():
                if result.is_final:
                    if self._stale_finals:
                        self._stale_finals -= 1
                        continue
                    if result.text.strip():
                        self._finals.append(result.text.strip())
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
    )
