"""The bridge that lets the model write and someone else speak.

Wraps a conversation bridge running in text mode and routes its text deltas into
a streaming TTS session, so the audio the caller hears is produced by a provider
chosen for its language rather than by the reasoning model. This is the one place
in the codebase where the ``conversation`` and ``streaming_tts`` seams meet; both
provider vocabularies still stop at their own seams, and the runtime above sees
the ordinary ``RealtimeBridge`` vocabulary either way.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from functools import partial
from typing import Any

import structlog

from assemblix_api.external.voice import speech_out as speech_out_module
from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    BridgeError,
    BridgeEvent,
    RealtimeBridge,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
)
from assemblix_api.external.voice.speech_out import SpeechOutput
from assemblix_api.external.voice.streaming_tts import RealtimeSession
from assemblix_api.schemas.debug_events import AlignmentData

logger = structlog.get_logger(__name__)

OpenStream = Callable[..., RealtimeSession]


class HalfCascadeBridge:
    def __init__(
        self,
        *,
        inner: RealtimeBridge,
        speech_out: SpeechOutput,
        output_sample_rate: int,
        open_stream: OpenStream | None = None,
    ) -> None:
        self._inner = inner
        self.input_sample_rate = inner.input_sample_rate
        self.output_sample_rate = output_sample_rate
        self._speech_out = speech_out
        self._open_stream = open_stream or speech_out_module.open_stream
        self._queue: asyncio.Queue[BridgeEvent] = asyncio.Queue()
        self._session: RealtimeSession | None = None
        self._channel: Any = None
        # Turns are counted so a cancelled one can be named. Text the model had
        # already committed to arrives after the cancellation; without this it would
        # open a fresh session and the agent would speak after being interrupted.
        self._turn = 0
        self._cancelled_turn = -1
        self._turn_chars = 0
        # What of this turn's reply has already gone to the synthesizer. The two
        # bridges disagree about what ``AgentTranscript.text`` holds — OpenAI
        # streams deltas but repeats the whole reply on the final event, Gemini
        # accumulates from the first — so the only safe reading is "the reply so
        # far", and only its unspoken tail may be spoken.
        self._spoken = ""
        # Bumped on every abort; audio from a session opened under an older value is dropped.
        self._speech_epoch = 0
        self._session_chars = 0
        # A finished reply keeps playing for seconds after the model is done; its flush
        # runs off the pump so a barge-in is not held behind it. The final transcript
        # and TurnEnded of that turn wait on ``_pending`` instead.
        self._flushing: tuple[RealtimeSession, asyncio.Task[int]] | None = None
        self._pending: asyncio.Task[None] | None = None
        # Whether the inner bridge is mid-turn; past its TurnEnded, only a bridge that
        # accepts late interrupts is told about a barge-in.
        self._turn_open = False

    @property
    def accepts_late_interrupt(self) -> bool:
        return bool(getattr(self._inner, "accepts_late_interrupt", False))

    async def connect(
        self,
        *,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
        text_output: bool = False,
    ) -> None:
        self._channel = speech_out_module.open_channel(self._speech_out)
        try:
            await self._inner.connect(
                instructions=instructions,
                voice=voice,
                language=language,
                params=params,
                text_output=True,
            )
        except BaseException:
            await self._close_channel()
            raise

    async def send_audio(self, pcm: bytes) -> None:
        await self._inner.send_audio(pcm)

    async def interrupt(self, *, audio_end_ms: int) -> None:
        await self._abort_speech()
        if self._turn_open or self.accepts_late_interrupt:
            await self._inner.interrupt(audio_end_ms=audio_end_ms)

    async def events(self) -> AsyncIterator[BridgeEvent]:
        pump = asyncio.create_task(self._pump_inner())
        try:
            while True:
                event = await self._queue.get()
                yield event
                if isinstance(event, SessionClosed):
                    return
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump
            await self._cancel_pending()

    async def _pump_inner(self) -> None:
        async for event in self._inner.events():
            match event:
                case AgentTranscript():
                    self._turn_open = True
                    await self._speak(event)
                    if event.is_final:
                        await self._in_order(partial(self._queue.put, event))
                    else:
                        await self._queue.put(event)
                case SpeechStarted():
                    # Plain voice-activity detection, not a barge-in: it precedes
                    # every turn. Only speech already in flight can be cancelled —
                    # cancelling unconditionally would let the caller's first word
                    # silence the agent for the rest of the call. Same guard the
                    # runtime applies with ``_agent_speaking``.
                    if self._session is not None:
                        self._cancelled_turn = self._turn
                        self._spoken = ""
                        await self._abort_speech()
                    elif self._flushing is not None:
                        await self._abort_speech()
                    await self._queue.put(event)
                case TurnEnded():
                    self._turn_open = False
                    self._turn += 1
                    self._spoken = ""
                    await self._in_order(partial(self._end_turn, event))
                case SessionClosed():
                    await self._drain()
                    await self._queue.put(event)
                case _:
                    await self._queue.put(event)
        await self._drain()
        # An inner bridge always ends with SessionClosed; this keeps one that does
        # not from hanging the consumer on an empty queue.
        await self._queue.put(SessionClosed(reason="inner_ended"))

    async def _end_turn(self, event: TurnEnded) -> None:
        chars, self._turn_chars = self._turn_chars, 0
        usage = event.usage
        if usage is not None:
            try:
                tts_cost: float | None = float(speech_out_module.cost_usd(self._speech_out, chars))
            except ValueError:
                tts_cost = None
            usage = {**usage, "ttsChars": chars, "ttsCostUsd": tts_cost}
        await self._queue.put(
            replace(event, speech_chars=chars or None, usage=usage),
        )

    async def _in_order(self, step: Callable[[], Awaitable[None]]) -> None:
        """Run ``step`` now, or after the pending flush when one is still running."""
        previous = self._pending
        if previous is None or previous.done():
            self._pending = None
            await step()
            return

        async def after_previous() -> None:
            await asyncio.wait({previous})
            await step()

        self._pending = asyncio.create_task(after_previous())

    async def _drain(self) -> None:
        if self._pending is not None:
            await asyncio.wait({self._pending})
            self._pending = None

    async def _cancel_pending(self) -> None:
        pending, self._pending = self._pending, None
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.wait({pending})

    async def _speak(self, event: AgentTranscript) -> None:
        if self._turn == self._cancelled_turn:
            return
        text = self._unspoken(event.text)
        if not text and not event.is_final:
            return
        if self._session is None:
            # Two sessions synthesizing at once would interleave their audio.
            await self._drain()
            epoch = self._speech_epoch

            async def on_audio(pcm: bytes, alignment: AlignmentData | None) -> None:
                if epoch == self._speech_epoch:
                    await self._on_audio(pcm, alignment)

            async def on_error(message: str) -> None:
                if epoch == self._speech_epoch:
                    await self._on_error(message)

            self._session_chars = 0
            self._session = self._open_stream(
                self._speech_out,
                on_audio=on_audio,
                on_error=on_error,
                channel=self._channel,
            )
            session = self._session
            await session.open()
            # An interrupt() may have aborted the session while it was opening.
            if self._session is not session:
                return
        session = self._session
        if text:
            self._session_chars += len(text)
            await session.send_text(text)
            if self._session is not session:
                return
        if event.is_final:
            self._session = None
            self._spoken = ""
            self._start_flush(session)

    def _start_flush(self, session: RealtimeSession) -> None:
        flush = asyncio.create_task(session.flush_and_close())
        self._flushing = (session, flush)
        sent = self._session_chars
        previous = self._pending

        async def finish() -> None:
            await asyncio.wait({flush})
            if self._flushing is not None and self._flushing[1] is flush:
                self._flushing = None
            if flush.cancelled():
                # Aborted by a barge-in: everything was already sent and billed.
                self._turn_chars += sent
            elif (exc := flush.exception()) is not None:
                logger.warning("voice.half_cascade.flush_failed", error=str(exc))
                self._turn_chars += sent
            else:
                self._turn_chars += flush.result()
            if previous is not None:
                await asyncio.wait({previous})

        self._pending = asyncio.create_task(finish())

    def _unspoken(self, text: str) -> str:
        """The part of ``text`` not yet handed to the synthesizer.

        Accumulated text extends what was spoken; a delta does not, and is taken
        as the extension itself.
        """
        tail = text[len(self._spoken) :] if text.startswith(self._spoken) else text
        self._spoken += tail
        return tail

    async def _abort_speech(self) -> None:
        self._speech_epoch += 1
        flushing, self._flushing = self._flushing, None
        session, self._session = self._session, None
        if session is not None:
            self._turn_chars += self._session_chars
        try:
            if flushing is not None:
                # Cancelled before the socket closes, so the provider's reader stops
                # quietly instead of reporting a dead connection.
                flushing[1].cancel()
                await asyncio.wait({flushing[1]})
        finally:
            for to_close in (flushing[0] if flushing else None, session):
                if to_close is not None:
                    with contextlib.suppress(Exception):
                        await to_close.aclose()

    async def _on_audio(self, pcm: bytes, alignment: AlignmentData | None) -> None:
        await self._queue.put(AudioDelta(pcm=pcm))

    async def _on_error(self, message: str) -> None:
        logger.warning("voice.half_cascade.tts_failed", error=message)
        await self._queue.put(BridgeError(code="tts_unavailable", message=message, is_fatal=True))

    async def close(self) -> None:
        await self._abort_speech()
        await self._cancel_pending()
        await self._inner.close()
        await self._close_channel()

    async def _close_channel(self) -> None:
        channel, self._channel = self._channel, None
        if channel is not None:
            with contextlib.suppress(Exception):
                await channel.close()
