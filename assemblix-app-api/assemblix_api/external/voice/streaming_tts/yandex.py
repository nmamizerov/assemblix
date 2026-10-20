"""Yandex SpeechKit v3 realtime text-to-speech over gRPC.

The sibling of ``realtime.py`` (ElevenLabs) for the avatar / realtime-voice path. It
exposes the same duck-typed session contract — ``open() / send_text() / flush_and_close()``
plus an ``on_audio(pcm, alignment)`` callback — so the agent node stays provider-agnostic.

SpeechKit v3 offers two streaming RPCs, surfaced here as ``mode``:

* ``"utterance"`` / ``"chunk"`` — cut the text into segments (see ``Segmenter``) and
  synthesize each with ``UtteranceSynthesis``. SpeechKit returns a segment's audio only
  after synthesizing most of it, so up to three segments are synthesized ahead while
  earlier ones play; audio is still forwarded strictly in order.
* ``"stream"`` — send the same segments over ``StreamSynthesis`` (bidirectional), forcing
  synthesis at each segment boundary.

Both emit raw ``LINEAR16_PCM`` at 16 kHz mono — exactly what anam's audio passthrough
expects — so no resampling is needed. Live/best-effort: a gRPC error stops audio but never
raises out of ``send_text``/``flush_and_close``; the caller's text stream is unaffected.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

from assemblix_api.core.settings import get_settings
from assemblix_api.external.voice.providers.yandex import split_credential
from assemblix_api.schemas.debug_events import AlignmentData

logger = structlog.get_logger(__name__)

OnAudio = Callable[[bytes, AlignmentData | None], Awaitable[None]]
OnError = Callable[[str], Awaitable[None]]

Mode = Literal["utterance", "stream", "chunk"]

# anam passthrough is pcm_s16le / 16000 / mono — request exactly that from SpeechKit.
YANDEX_SAMPLE_RATE = 16000

# Segments grow along the reply: a short first clause gets audio out fast, and each
# later segment is synthesized while the earlier ones play.
_SENTENCE_END = re.compile(r"[.!?…]+(?=\s|$)|\n")
_CLAUSE_END = re.compile(r"[,;:](?=\s)|\s[—–-](?=\s)")
_SPACE = re.compile(r"\s")
_FIRST_MAX = 80
_FIRST_MIN_CLAUSE = 20
_RAMP_MAX = 140
_CHUNK_CHARS = 250
_MAX_IN_FLIGHT = 3
_BYTES_PER_MS = YANDEX_SAMPLE_RATE * 2 // 1000

# Sentinel that tells a worker loop no more text is coming.
_DONE = object()


def _space_cut(text: str, limit: int) -> int | None:
    """End of the last whole word within ``limit``, else of the first word past it."""
    cut = text.rfind(" ", 0, limit + 1)
    if cut > 0:
        return cut
    cut = text.find(" ", limit)
    return cut if cut > 0 else None


def _long_cut(text: str, limit: int) -> int | None:
    clauses = [m.end() for m in _CLAUSE_END.finditer(text) if m.end() <= limit]
    return clauses[-1] if clauses else _space_cut(text, limit)


def _split_long(text: str, limit: int) -> list[str]:
    """Halve ``text`` at the clause boundary nearest its middle until it fits ``limit``."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    size = len(text)
    clauses = [m.end() for m in _CLAUSE_END.finditer(text) if size / 4 <= m.end() <= size * 3 / 4]
    cuts = clauses or [m.start() for m in _SPACE.finditer(text) if m.start() > 0]
    if not cuts:
        return [text]
    cut = min(cuts, key=lambda c: abs(c - size / 2))
    return _split_long(text[:cut], limit) + _split_long(text[cut:], limit)


class Segmenter:
    """Cuts streamed text into synthesis segments.

    The first segment ends at the first sentence end or clause boundary (max ~80
    chars), the second fits in ~140, and the rest are sentences — one per segment,
    long ones halved at a clause, or packed up to 250 chars with ``pack``.
    """

    def __init__(self, *, pack: bool) -> None:
        self._pack = pack
        self._buffer = ""
        self._pending = ""
        self._count = 0

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        return self._drain(final=False)

    def flush(self) -> list[str]:
        out = self._drain(final=True)
        if self._pending:
            out.append(self._pending)
            self._pending = ""
            self._count += 1
        return out

    def _drain(self, *, final: bool) -> list[str]:
        out: list[str] = []
        while units := self._next_units(final):
            for unit in units:
                out.extend(self._emit(unit))
        return out

    def _next_units(self, final: bool) -> list[str]:
        buf = self._buffer = self._buffer.lstrip()
        if not buf:
            return []
        if self._count == 0:
            cut = self._first_cut(buf)
            limit = _FIRST_MAX
        else:
            limit = _CHUNK_CHARS if self._pack and self._count >= 2 else _RAMP_MAX
            sentence = _SENTENCE_END.search(buf)
            if sentence is not None:
                cut = sentence.end()
            elif len(buf) > limit:
                cut = _long_cut(buf, limit)
            else:
                cut = None
        if cut is None:
            if not final:
                return []
            cut = len(buf)
        self._buffer = buf[cut:]
        return _split_long(buf[:cut], limit)

    @staticmethod
    def _first_cut(buf: str) -> int | None:
        cuts = []
        if (sentence := _SENTENCE_END.search(buf)) is not None:
            cuts.append(sentence.end())
        clause = next(
            (m.end() for m in _CLAUSE_END.finditer(buf) if m.end() >= _FIRST_MIN_CLAUSE), None
        )
        if clause is not None:
            cuts.append(clause)
        if cuts and min(cuts) <= _FIRST_MAX:
            return min(cuts)
        if len(buf) > _FIRST_MAX:
            return _space_cut(buf, _FIRST_MAX)
        return None

    def _emit(self, unit: str) -> list[str]:
        if not self._pack or self._count < 2:
            self._count += 1
            return [unit]
        out: list[str] = []
        candidate = f"{self._pending} {unit}".strip()
        if self._pending and len(candidate) > _CHUNK_CHARS:
            out.append(self._pending)
            self._count += 1
            self._pending = unit
        else:
            self._pending = candidate
        if len(self._pending) >= _CHUNK_CHARS:
            out.append(self._pending)
            self._count += 1
            self._pending = ""
        return out


@dataclass
class _Segment:
    index: int
    text: str
    queued_at: float
    audio: asyncio.Queue[Any] = field(default_factory=asyncio.Queue)


class YandexRealtimeSession:
    def __init__(
        self,
        *,
        credential: str,
        voice_id: str,
        model: str,
        on_audio: OnAudio,
        mode: Mode = "utterance",
        stub: Any = None,
        on_error: OnError | None = None,
        channel: Any = None,
    ):
        # ``credential`` is the combined "<folderId>:<apiKey>" form; split at open().
        self._credential = credential
        self._voice_id = voice_id
        self._model = model  # our catalog id (unused as a SpeechKit model name)
        self._on_audio = on_audio
        self._on_error = on_error
        self._mode: Mode = mode
        self._stub = stub  # injectable for tests; a real aio stub is built in open()
        # A channel owned by the caller outlives this session; only our own is closed.
        self._shared_channel = channel
        self._channel: Any = None
        self._metadata: list[tuple[str, str]] = []
        self._segmenter = Segmenter(pack=mode == "chunk")
        self._segments = 0
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._chars_sent = 0
        self._failed = False
        self._closed = False
        self._call: Any = None
        self._calls: set[Any] = set()
        self._fetches: set[asyncio.Task] = set()
        self._slots = asyncio.Semaphore(_MAX_IN_FLIGHT)

    async def _fail(self, event: str, exc: BaseException) -> None:
        """Audio is best-effort here, but a caller that owns a live call has to hear
        about a dead provider rather than infer it from silence."""
        self._failed = True
        message = str(exc)
        logger.info(event, error=message)
        if self._on_error is not None:
            await self._on_error(message)

    # -- lifecycle ----------------------------------------------------------------

    async def open(self) -> None:
        folder_id, api_key = split_credential(self._credential)  # raises ValueError
        self._metadata = [
            ("authorization", f"Api-Key {api_key}"),
            ("x-folder-id", folder_id),
        ]
        if self._stub is None:
            from yandex.cloud.ai.tts.v3 import tts_service_pb2_grpc

            channel = self._shared_channel
            if channel is None:
                import grpc

                endpoint = get_settings().yandex_tts_v3_grpc_endpoint
                channel = self._channel = grpc.aio.secure_channel(
                    endpoint, grpc.ssl_channel_credentials()
                )
            self._stub = tts_service_pb2_grpc.SynthesizerStub(channel)

        stream = self._mode == "stream"
        worker = self._stream_worker if stream else self._utterance_worker
        self._worker = asyncio.create_task(worker())

    async def send_text(self, text: str) -> None:
        if self._failed or self._closed or not text:
            return
        self._chars_sent += len(text)
        self._enqueue(self._segmenter.feed(text))

    def _enqueue(self, texts: list[str]) -> None:
        for text in texts:
            self._queue.put_nowait(_Segment(self._segments, text, time.monotonic()))
            self._segments += 1

    async def flush_and_close(self) -> int:
        if not self._failed:
            self._enqueue(self._segmenter.flush())
        await self._queue.put(_DONE)
        if self._worker is not None:
            try:
                await asyncio.wait_for(self._worker, timeout=60.0)
            except Exception:  # noqa: BLE001 — audio is best-effort; abandon the worker.
                self._worker.cancel()
        await self.aclose()
        return self._chars_sent

    async def aclose(self) -> None:
        self._closed = True
        # A shared channel is not closed below, so in-flight RPCs must be stopped here.
        for call in (self._call, *self._calls):
            if call is not None:
                with contextlib.suppress(Exception):
                    call.cancel()
        worker = self._worker
        if worker is not None and not worker.done() and worker is not asyncio.current_task():
            worker.cancel()
            await asyncio.wait({worker})
        if self._channel is not None:
            with contextlib.suppress(Exception):
                await self._channel.close()
            self._channel = None

    # -- utterance / chunk mode (UtteranceSynthesis, segments synthesized ahead) ---

    async def _utterance_worker(self) -> None:
        order: asyncio.Queue[Any] = asyncio.Queue()
        forwarder = asyncio.create_task(self._forward(order))
        try:
            while True:
                segment = await self._queue.get()
                if segment is _DONE or self._failed:
                    break
                await self._slots.acquire()
                fetch = asyncio.create_task(self._synthesize_utterance(segment))
                self._fetches.add(fetch)
                fetch.add_done_callback(self._fetch_done)
                order.put_nowait(segment)
            order.put_nowait(_DONE)
            await asyncio.wait({forwarder})
        finally:
            tasks = {forwarder, *self._fetches}
            for task in tasks:
                task.cancel()
            await asyncio.wait(tasks)

    def _fetch_done(self, task: asyncio.Task) -> None:
        self._fetches.discard(task)
        self._slots.release()

    async def _forward(self, order: asyncio.Queue[Any]) -> None:
        """Play segments strictly in order, whichever finished synthesizing first."""
        try:
            while (segment := await order.get()) is not _DONE:
                while (item := await segment.audio.get()) is not _DONE:
                    if isinstance(item, BaseException):
                        raise item
                    if self._closed:
                        return
                    await self._on_audio(item, None)
        except Exception as exc:  # noqa: BLE001 — best-effort; log and stop audio.
            for fetch in self._fetches:
                fetch.cancel()
            await self._fail("voice.realtime.yandex.utterance_stopped", exc)

    async def _synthesize_utterance(self, segment: _Segment) -> None:
        from yandex.cloud.ai.tts.v3 import tts_pb2

        request = tts_pb2.UtteranceSynthesisRequest(
            text=segment.text,
            hints=[tts_pb2.Hints(voice=self._voice_id)],
            output_audio_spec=_audio_spec(tts_pb2),
        )
        started_at = time.monotonic()
        first_audio_at: float | None = None
        audio_bytes = 0
        call = self._stub.UtteranceSynthesis(request, metadata=self._metadata)
        self._calls.add(call)
        try:
            async for response in call:
                data = response.audio_chunk.data
                if data:
                    if first_audio_at is None:
                        first_audio_at = time.monotonic()
                    audio_bytes += len(data)
                    segment.audio.put_nowait(data)
            segment.audio.put_nowait(_DONE)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                call.cancel()
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced in order by the forwarder.
            segment.audio.put_nowait(exc)
        finally:
            self._calls.discard(call)
        logger.info(
            "voice.tts.request",
            mode=self._mode,
            segment=segment.index,
            chars=len(segment.text),
            queued_ms=round((started_at - segment.queued_at) * 1000),
            first_audio_ms=(
                None if first_audio_at is None else round((first_audio_at - started_at) * 1000)
            ),
            audio_ms=audio_bytes // _BYTES_PER_MS,
        )

    # -- stream mode (StreamSynthesis, bidirectional) -----------------------------

    async def _stream_worker(self) -> None:
        from yandex.cloud.ai.tts.v3 import tts_pb2

        try:
            responses = self._call = self._stub.StreamSynthesis(
                self._stream_requests(tts_pb2), metadata=self._metadata
            )
            async for response in responses:
                data = response.audio_chunk.data
                if data:
                    await self._on_audio(data, None)
        except Exception as exc:  # noqa: BLE001 — best-effort; log and stop audio.
            await self._fail("voice.realtime.yandex.stream_stopped", exc)

    async def _stream_requests(self, tts_pb2: Any) -> AsyncIterator[Any]:
        # First message carries the synthesis options; the rest carry text segments,
        # each forced out so a clause is spoken without waiting for its sentence end.
        yield tts_pb2.StreamSynthesisRequest(
            options=tts_pb2.SynthesisOptions(
                voice=self._voice_id,
                output_audio_spec=_audio_spec(tts_pb2),
            )
        )
        while True:
            segment = await self._queue.get()
            if segment is _DONE:
                return
            yield tts_pb2.StreamSynthesisRequest(
                synthesis_input=tts_pb2.SynthesisInput(text=segment.text)
            )
            yield tts_pb2.StreamSynthesisRequest(force_synthesis=tts_pb2.ForceSynthesisEvent())

    async def __aenter__(self) -> YandexRealtimeSession:
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.flush_and_close()


def _audio_spec(tts_pb2: Any) -> Any:
    """AudioFormatOptions for raw 16 kHz mono LINEAR16 PCM (anam-native)."""
    return tts_pb2.AudioFormatOptions(
        raw_audio=tts_pb2.RawAudio(
            audio_encoding=tts_pb2.RawAudio.LINEAR16_PCM,
            sample_rate_hertz=YANDEX_SAMPLE_RATE,
        )
    )
