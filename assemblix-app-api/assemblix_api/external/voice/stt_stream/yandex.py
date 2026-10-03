"""Yandex SpeechKit v3 streaming recognition over gRPC.

One channel per call. A recognition stream opens on the first audio and reopens on
the next audio after the server ends it; phrases are finalised only when we send
``Eou`` (external end-of-utterance classifier), because turn-taking is decided
locally.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
from collections.abc import AsyncIterator
from typing import Any

import structlog
from yandex.cloud.ai.stt.v3 import stt_pb2

from assemblix_api.core.settings import get_settings
from assemblix_api.external.voice.providers.yandex import split_credential
from assemblix_api.external.voice.stt_stream import SttResult, SttUnavailable

logger = structlog.get_logger(__name__)

_SAMPLE_RATE = 16000
_BYTES_PER_SECOND = _SAMPLE_RATE * 2
_BILLING_UNIT_SECONDS = 15
_MAX_FAILURES = 3
_LANGUAGES = {"ru": "ru-RU", "en": "en-US", "kk": "kk-KZ", "uz": "uz-UZ", "tr": "tr-TR"}


class YandexSttStream:
    def __init__(self, *, credential: str, model: str = "general", stub: Any = None) -> None:
        self._credential = credential
        self._model = model
        self._stub = stub
        self._channel: Any = None
        self._metadata: list[tuple[str, str]] = []
        self._language = "ru-RU"
        self._requests: asyncio.Queue[Any] | None = None
        self._reader: asyncio.Task[None] | None = None
        self._results: asyncio.Queue[SttResult | Exception | None] = asyncio.Queue()
        self._stream_bytes = 0
        self._billed = 0.0
        self._failures = 0
        self._closed = False

    @property
    def billed_seconds(self) -> float:
        return self._billed

    async def open(self, *, language: str) -> None:
        folder_id, api_key = split_credential(self._credential)
        self._metadata = [("authorization", f"Api-Key {api_key}"), ("x-folder-id", folder_id)]
        self._language = _LANGUAGES.get(language, language)
        if self._stub is None:
            import grpc
            from yandex.cloud.ai.stt.v3 import stt_service_pb2_grpc

            endpoint = get_settings().yandex_stt_v3_grpc_endpoint
            self._channel = grpc.aio.secure_channel(endpoint, grpc.ssl_channel_credentials())
            self._stub = stt_service_pb2_grpc.RecognizerStub(self._channel)

    async def send_audio(self, pcm: bytes) -> None:
        if self._closed or not pcm:
            return
        if self._requests is None:
            self._start_stream()
        assert self._requests is not None
        self._stream_bytes += len(pcm)
        await self._requests.put(stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=pcm)))

    async def finalize(self) -> None:
        if self._requests is not None:
            await self._requests.put(stt_pb2.StreamingRequest(eou=stt_pb2.Eou()))

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
        if self._requests is not None:
            self._requests.put_nowait(None)
        if self._reader is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._reader, timeout=1.0)
            if not self._reader.done():
                self._reader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._reader
        self._results.put_nowait(None)
        if self._channel is not None:
            with contextlib.suppress(Exception):
                await self._channel.close()
            self._channel = None

    def _start_stream(self) -> None:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        queue.put_nowait(self._options())
        self._requests = queue
        call = self._stub.RecognizeStreaming(_drain(queue), metadata=self._metadata)
        self._reader = asyncio.create_task(self._read(call, queue))

    async def _read(self, call: Any, queue: asyncio.Queue[Any]) -> None:
        try:
            async for response in call:
                result = _to_result(response)
                if result is None:
                    continue
                if result.is_final:
                    self._failures = 0
                await self._results.put(result)
        except Exception as exc:  # noqa: BLE001 — any transport error counts as a failed stream.
            self._failures += 1
            logger.info("voice.stt.yandex.stream_failed", error=str(exc), failures=self._failures)
            if self._failures >= _MAX_FAILURES:
                await self._results.put(SttUnavailable(str(exc)))
        finally:
            self._end_stream(queue)

    def _end_stream(self, queue: asyncio.Queue[Any]) -> None:
        queue.put_nowait(None)
        if self._requests is queue:
            self._requests = None
        if self._stream_bytes:
            seconds = self._stream_bytes / _BYTES_PER_SECOND
            self._billed += math.ceil(seconds / _BILLING_UNIT_SECONDS) * _BILLING_UNIT_SECONDS
        self._stream_bytes = 0

    def _options(self) -> Any:
        return stt_pb2.StreamingRequest(
            session_options=stt_pb2.StreamingOptions(
                recognition_model=stt_pb2.RecognitionModelOptions(
                    model=self._model,
                    audio_format=stt_pb2.AudioFormatOptions(
                        raw_audio=stt_pb2.RawAudio(
                            audio_encoding=stt_pb2.RawAudio.LINEAR16_PCM,
                            sample_rate_hertz=_SAMPLE_RATE,
                            audio_channel_count=1,
                        )
                    ),
                    text_normalization=stt_pb2.TextNormalizationOptions(
                        text_normalization=stt_pb2.TextNormalizationOptions.TEXT_NORMALIZATION_ENABLED,
                    ),
                    language_restriction=stt_pb2.LanguageRestrictionOptions(
                        restriction_type=stt_pb2.LanguageRestrictionOptions.WHITELIST,
                        language_code=[self._language],
                    ),
                    audio_processing_type=stt_pb2.RecognitionModelOptions.REAL_TIME,
                ),
                eou_classifier=stt_pb2.EouClassifierOptions(
                    external_classifier=stt_pb2.ExternalEouClassifier()
                ),
            )
        )


async def _drain(queue: asyncio.Queue[Any]) -> AsyncIterator[Any]:
    while True:
        item = await queue.get()
        if item is None:
            return
        yield item


def _to_result(response: Any) -> SttResult | None:
    event = response.WhichOneof("Event")
    if event not in ("partial", "final"):
        return None
    update = getattr(response, event)
    text = update.alternatives[0].text if update.alternatives else ""
    return SttResult(text=text, is_final=event == "final")
