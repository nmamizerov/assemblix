"""T-one self-hosted streaming recognition over its WebSocket demo protocol.

The server is lock-step: it sends ``{"event": "ready"}`` before every receive, takes
one binary message of 8 kHz PCM16, and treats an empty message as end of stream —
it then flushes the remaining phrases and closes. One connection carries one
utterance: ``finalize()`` ends it and the next audio opens a fresh one. T-one has no
partials, so phrases found mid-utterance are surfaced as previews and the whole
utterance becomes a single final when the server closes.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

import numpy as np
import structlog
import websockets

from assemblix_api.core.settings import get_settings
from assemblix_api.external.voice.stt_stream import SttResult, SttUnavailable

logger = structlog.get_logger(__name__)

_INPUT_RATE = 16000
_OUTPUT_RATE = 8000
# T-one consumes 300 ms chunks; sending less per round trip only adds round trips.
_SEND_BYTES = _OUTPUT_RATE * 3 // 10 * 2
_MAX_FAILURES = 3
_CONNECT_TIMEOUT = 5.0


def _lowpass_taps(count: int = 63, cutoff_hz: float = 3600.0) -> np.ndarray:
    n = np.arange(count) - (count - 1) / 2
    fc = cutoff_hz / _INPUT_RATE
    taps = 2 * fc * np.sinc(2 * fc * n) * np.blackman(count)
    return (taps / taps.sum()).astype(np.float32)


_TAPS = _lowpass_taps()


class Downsampler:
    """16 kHz → 8 kHz PCM16 with an anti-aliasing FIR whose state spans chunks."""

    def __init__(self) -> None:
        self._history = np.zeros(len(_TAPS) - 1, dtype=np.float32)
        self._phase = 0
        self._odd_byte = b""

    def process(self, pcm: bytes) -> bytes:
        data = self._odd_byte + pcm
        usable = len(data) - len(data) % 2
        self._odd_byte = data[usable:]
        if not usable:
            return b""
        samples = np.frombuffer(data[:usable], dtype="<i2").astype(np.float32)
        buffer = np.concatenate([self._history, samples])
        self._history = buffer[-(len(_TAPS) - 1) :]
        filtered = np.convolve(buffer, _TAPS, mode="valid")[self._phase :: 2]
        self._phase = (self._phase + len(samples)) % 2
        return np.clip(np.rint(filtered), -32768, 32767).astype("<i2").tobytes()


class _Utterance:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.finalizing = False
        self.sent_end = False
        self.phrases: list[str] = []
        self.wake = asyncio.Event()
        self.task: asyncio.Task[None] | None = None

    async def next_message(self) -> bytes:
        while True:
            if len(self.buffer) >= _SEND_BYTES or (self.finalizing and self.buffer):
                message = bytes(self.buffer)
                self.buffer.clear()
                return message
            if self.finalizing:
                self.sent_end = True
                return b""
            self.wake.clear()
            await self.wake.wait()


class ToneSttStream:
    def __init__(self, *, url: str | None = None) -> None:
        self._url = url if url is not None else get_settings().tone_stt_url
        self._results: asyncio.Queue[SttResult | Exception | None] = asyncio.Queue()
        self._current: _Utterance | None = None
        self._downsampler = Downsampler()
        self._tasks: set[asyncio.Task[None]] = set()
        self._failures = 0
        self._unavailable = False
        self._closed = False
        self._sent_bytes = 0

    @property
    def billed_seconds(self) -> float:
        return 0.0

    @property
    def sent_seconds(self) -> float:
        return self._sent_bytes / (_OUTPUT_RATE * 2)

    async def open(self, *, language: str) -> None:
        # T-one only recognises Russian; nothing to negotiate up front.
        return None

    async def send_audio(self, pcm: bytes) -> None:
        if self._closed or self._unavailable or not pcm:
            return
        utterance = self._current
        if utterance is None:
            utterance = self._start()
        utterance.buffer += self._downsampler.process(pcm)
        utterance.wake.set()

    async def finalize(self) -> None:
        utterance = self._current
        if utterance is None:
            # Nothing in flight (e.g. the stream died): answer at once, not by timeout.
            await self._results.put(SttResult(text="", is_final=True))
            return
        self._current = None
        utterance.finalizing = True
        utterance.wake.set()

    async def results(self) -> AsyncIterator[SttResult]:
        while True:
            item = await self._results.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    async def close(self) -> None:
        self._closed = True
        self._current = None
        for task in list(self._tasks):
            task.cancel()
            with contextlib.suppress(BaseException):
                await task
        self._results.put_nowait(None)

    def _start(self) -> _Utterance:
        utterance = _Utterance()
        self._current = utterance
        self._downsampler = Downsampler()
        task = asyncio.create_task(self._run(utterance))
        utterance.task = task
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return utterance

    async def _run(self, utterance: _Utterance) -> None:
        failed: Exception | None = None
        try:
            async with websockets.connect(
                self._url, open_timeout=_CONNECT_TIMEOUT, max_size=None
            ) as ws:
                self._failures = 0
                async for message in ws:
                    if isinstance(message, bytes):
                        continue
                    event = json.loads(message)
                    if event.get("event") == "ready":
                        if utterance.sent_end:
                            continue
                        payload = await utterance.next_message()
                        self._sent_bytes += len(payload)
                        await ws.send(payload)
                    elif event.get("event") == "transcript":
                        text = str(event.get("phrase", {}).get("text", "")).strip()
                        if text:
                            utterance.phrases.append(text)
                        if text and not utterance.finalizing:
                            await self._results.put(
                                SttResult(text=" ".join(utterance.phrases), is_final=False)
                            )
            if not utterance.sent_end:
                failed = ConnectionError("T-one closed the stream before it ended")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — any transport error counts as a failed stream.
            failed = exc
        if self._current is utterance:
            self._current = None
        if failed is not None:
            self._failures += 1
            logger.info("voice.stt.tone.stream_failed", error=str(failed), failures=self._failures)
            if self._failures >= _MAX_FAILURES:
                self._unavailable = True
                await self._results.put(SttUnavailable(str(failed)))
                return
        if utterance.finalizing:
            await self._results.put(SttResult(text=" ".join(utterance.phrases), is_final=True))
