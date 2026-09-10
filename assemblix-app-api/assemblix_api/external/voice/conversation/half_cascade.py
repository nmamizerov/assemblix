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
from collections.abc import AsyncIterator, Callable

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
        # Turns are counted so a cancelled one can be named. Text the model had
        # already committed to arrives after the cancellation; without this it would
        # open a fresh session and the agent would speak after being interrupted.
        self._turn = 0
        self._cancelled_turn = -1
        self._turn_chars = 0

    async def connect(
        self,
        *,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
        text_output: bool = False,
    ) -> None:
        await self._inner.connect(
            instructions=instructions,
            voice=voice,
            language=language,
            params=params,
            text_output=True,
        )

    async def send_audio(self, pcm: bytes) -> None:
        await self._inner.send_audio(pcm)

    async def interrupt(self, *, audio_end_ms: int) -> None:
        await self._abort_speech()
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

    async def _pump_inner(self) -> None:
        async for event in self._inner.events():
            match event:
                case AgentTranscript():
                    await self._speak(event)
                    await self._queue.put(event)
                case SpeechStarted():
                    # Stop speaking here rather than waiting for the runtime's
                    # interrupt(): the runtime only calls it while the agent is
                    # audibly speaking, and a session opened but not yet heard from
                    # would otherwise stay open for the rest of the call.
                    self._cancelled_turn = self._turn
                    await self._abort_speech()
                    await self._queue.put(event)
                case TurnEnded():
                    chars, self._turn_chars = self._turn_chars, 0
                    self._turn += 1
                    await self._queue.put(
                        TurnEnded(
                            input_tokens=event.input_tokens,
                            output_tokens=event.output_tokens,
                            speech_chars=chars or None,
                        )
                    )
                case _:
                    await self._queue.put(event)
        # An inner bridge always ends with SessionClosed; this keeps one that does
        # not from hanging the consumer on an empty queue.
        await self._queue.put(SessionClosed(reason="inner_ended"))

    async def _speak(self, event: AgentTranscript) -> None:
        if self._turn == self._cancelled_turn:
            return
        if self._session is None:
            self._session = self._open_stream(
                self._speech_out, on_audio=self._on_audio, on_error=self._on_error
            )
            await self._session.open()
        await self._session.send_text(event.text)
        if event.is_final:
            session, self._session = self._session, None
            self._turn_chars += await session.flush_and_close()

    async def _abort_speech(self) -> None:
        if self._session is None:
            return
        session, self._session = self._session, None
        with contextlib.suppress(Exception):
            await session.aclose()

    async def _on_audio(self, pcm: bytes, alignment: AlignmentData | None) -> None:
        await self._queue.put(AudioDelta(pcm=pcm))

    async def _on_error(self, message: str) -> None:
        await self._queue.put(BridgeError(code="tts_unavailable", message=message, is_fatal=True))

    async def close(self) -> None:
        await self._abort_speech()
        await self._inner.close()
