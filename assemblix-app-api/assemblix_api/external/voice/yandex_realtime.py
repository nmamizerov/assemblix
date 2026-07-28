"""Yandex SpeechKit v3 realtime text-to-speech over gRPC.

The sibling of ``realtime.py`` (ElevenLabs) for the avatar / realtime-voice path. It
exposes the same duck-typed session contract — ``open() / send_text() / flush_and_close()``
plus an ``on_audio(pcm, alignment)`` callback — so the agent node stays provider-agnostic.

SpeechKit v3 offers two streaming RPCs, surfaced here as ``mode``:

* ``"utterance"`` — buffer incoming deltas and synthesize one *whole sentence* at a time
  (``UtteranceSynthesis``, server-streaming). Full-sentence context gives the best Russian
  prosody; audio still flows out per sentence as the agent generates.
* ``"stream"`` — forward each delta as it arrives (``StreamSynthesis``, bidirectional).
  Lowest latency, at some cost to prosody on mid-sentence fragments.

Both emit raw ``LINEAR16_PCM`` at 16 kHz mono — exactly what anam's audio passthrough
expects — so no resampling is needed. Live/best-effort: a gRPC error stops audio but never
raises out of ``send_text``/``flush_and_close``; the caller's text stream is unaffected.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

import structlog

from assemblix_api.core.settings import get_settings
from assemblix_api.external.voice.yandex import split_credential
from assemblix_api.schemas.debug_events import AlignmentData

logger = structlog.get_logger(__name__)

OnAudio = Callable[[bytes, AlignmentData | None], Awaitable[None]]

Mode = Literal["utterance", "stream"]

# anam passthrough is pcm_s16le / 16000 / mono — request exactly that from SpeechKit.
_SAMPLE_RATE = 16000

# A "complete" chunk ends on sentence-final punctuation or a newline; the trailing
# incomplete fragment stays buffered until more text (or flush) closes it.
_SENTENCE = re.compile(r"[^.!?…\n]*[.!?…\n]+", re.S)

# Sentinel that tells a worker loop no more text is coming.
_DONE = object()


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
    ):
        # ``credential`` is the combined "<folderId>:<apiKey>" form; split at open().
        self._credential = credential
        self._voice_id = voice_id
        self._model = model  # our catalog id (unused as a SpeechKit model name)
        self._on_audio = on_audio
        self._mode: Mode = mode
        self._stub = stub  # injectable for tests; a real aio stub is built in open()
        self._channel: Any = None
        self._metadata: list[tuple[str, str]] = []
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._buffer = ""
        self._chars_sent = 0
        self._failed = False

    # -- lifecycle ----------------------------------------------------------------

    async def open(self) -> None:
        folder_id, api_key = split_credential(self._credential)  # raises ValueError
        self._metadata = [
            ("authorization", f"Api-Key {api_key}"),
            ("x-folder-id", folder_id),
        ]
        if self._stub is None:
            import grpc
            from yandex.cloud.ai.tts.v3 import tts_service_pb2_grpc

            endpoint = get_settings().yandex_tts_v3_grpc_endpoint
            self._channel = grpc.aio.secure_channel(endpoint, grpc.ssl_channel_credentials())
            self._stub = tts_service_pb2_grpc.SynthesizerStub(self._channel)

        worker = self._utterance_worker if self._mode == "utterance" else self._stream_worker
        self._worker = asyncio.create_task(worker())

    async def send_text(self, text: str) -> None:
        if self._failed or not text:
            return
        self._chars_sent += len(text)
        if self._mode == "utterance":
            self._buffer += text
            for sentence in self._drain_sentences():
                await self._queue.put(sentence)
        else:
            await self._queue.put(text)

    async def flush_and_close(self) -> int:
        if self._mode == "utterance" and not self._failed:
            tail = self._buffer.strip()
            self._buffer = ""
            if tail:
                await self._queue.put(tail)
        await self._queue.put(_DONE)
        if self._worker is not None:
            try:
                await asyncio.wait_for(self._worker, timeout=60.0)
            except Exception:  # noqa: BLE001 — audio is best-effort; abandon the worker.
                self._worker.cancel()
        await self.aclose()
        return self._chars_sent

    async def aclose(self) -> None:
        if self._channel is not None:
            with contextlib.suppress(Exception):
                await self._channel.close()
            self._channel = None

    # -- utterance mode (UtteranceSynthesis, one sentence per call) ----------------

    def _drain_sentences(self) -> list[str]:
        """Pull complete sentences out of the buffer, leaving the tail fragment."""
        out: list[str] = []
        last = 0
        for m in _SENTENCE.finditer(self._buffer):
            chunk = m.group().strip()
            if chunk:
                out.append(chunk)
            last = m.end()
        self._buffer = self._buffer[last:]
        return out

    async def _utterance_worker(self) -> None:
        try:
            while True:
                item = await self._queue.get()
                if item is _DONE:
                    return
                await self._synthesize_utterance(item)
        except Exception as exc:  # noqa: BLE001 — best-effort; log and stop audio.
            self._failed = True
            logger.info("voice.realtime.yandex.utterance_stopped", error=str(exc))

    async def _synthesize_utterance(self, text: str) -> None:
        from yandex.cloud.ai.tts.v3 import tts_pb2

        request = tts_pb2.UtteranceSynthesisRequest(
            text=text,
            hints=[tts_pb2.Hints(voice=self._voice_id)],
            output_audio_spec=_audio_spec(tts_pb2),
        )
        async for response in self._stub.UtteranceSynthesis(request, metadata=self._metadata):
            data = response.audio_chunk.data
            if data:
                await self._on_audio(data, None)

    # -- stream mode (StreamSynthesis, bidirectional) -----------------------------

    async def _stream_worker(self) -> None:
        from yandex.cloud.ai.tts.v3 import tts_pb2

        try:
            responses = self._stub.StreamSynthesis(
                self._stream_requests(tts_pb2), metadata=self._metadata
            )
            async for response in responses:
                data = response.audio_chunk.data
                if data:
                    await self._on_audio(data, None)
        except Exception as exc:  # noqa: BLE001 — best-effort; log and stop audio.
            self._failed = True
            logger.info("voice.realtime.yandex.stream_stopped", error=str(exc))

    async def _stream_requests(self, tts_pb2: Any) -> AsyncIterator[Any]:
        # First message carries the synthesis options; the rest carry text as it arrives.
        yield tts_pb2.StreamSynthesisRequest(
            options=tts_pb2.SynthesisOptions(
                voice=self._voice_id,
                output_audio_spec=_audio_spec(tts_pb2),
            )
        )
        while True:
            item = await self._queue.get()
            if item is _DONE:
                return
            yield tts_pb2.StreamSynthesisRequest(synthesis_input=tts_pb2.SynthesisInput(text=item))

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
            sample_rate_hertz=_SAMPLE_RATE,
        )
    )
