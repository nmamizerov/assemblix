import asyncio
from typing import Any

import pytest
from yandex.cloud.ai.stt.v3 import stt_pb2

from assemblix_api.external.voice.stt_stream import SttResult, SttUnavailable
from assemblix_api.external.voice.stt_stream.yandex import YandexSttStream


def _partial(text: str) -> Any:
    return stt_pb2.StreamingResponse(
        partial=stt_pb2.AlternativeUpdate(alternatives=[stt_pb2.Alternative(text=text)])
    )


def _final(text: str) -> Any:
    return stt_pb2.StreamingResponse(
        final=stt_pb2.AlternativeUpdate(alternatives=[stt_pb2.Alternative(text=text)])
    )


class _Call:
    """Consumes the request iterator; replies are scripted per received Eou."""

    def __init__(self, requests: Any, replies: list[Any], fail: Exception | None) -> None:
        self.requests: list[Any] = []
        self._source = requests
        self._replies = replies
        self._fail = fail

    async def __aiter__(self) -> Any:
        async for request in self._source:
            self.requests.append(request)
            if request.WhichOneof("Event") == "chunk" and self._replies:
                yield self._replies.pop(0)
            if request.WhichOneof("Event") == "eou":
                if self._fail is not None:
                    raise self._fail
                yield _final("привет мир")
                return


class _Stub:
    def __init__(self, replies: list[Any] | None = None, failures: int = 0) -> None:
        self.calls: list[_Call] = []
        self.metadata: list[Any] = []
        self._replies = replies or []
        self._failures = failures

    def RecognizeStreaming(self, requests: Any, metadata: Any = None) -> _Call:
        self.metadata.append(metadata)
        fail = RuntimeError("UNAVAILABLE") if self._failures > 0 else None
        self._failures -= 1
        call = _Call(requests, self._replies, fail)
        self.calls.append(call)
        return call


async def _collect(stream: YandexSttStream, count: int) -> list[SttResult]:
    out: list[SttResult] = []
    async for result in stream.results():
        out.append(result)
        if len(out) == count:
            break
    return out


async def test_partials_then_final_on_eou_with_expected_options() -> None:
    stub = _Stub(replies=[_partial("при")])
    stream = YandexSttStream(credential="b1folder:AQVN-key", stub=stub)
    await stream.open(language="ru")

    await stream.send_audio(b"\x00\x01" * 1600)
    await stream.finalize()
    results = await asyncio.wait_for(_collect(stream, 2), timeout=1)

    assert results == [SttResult("при", False), SttResult("привет мир", True)]
    options = stub.calls[0].requests[0].session_options
    assert options.recognition_model.audio_format.raw_audio.sample_rate_hertz == 16000
    assert list(options.recognition_model.language_restriction.language_code) == ["ru-RU"]
    assert options.eou_classifier.HasField("external_classifier")
    assert ("authorization", "Api-Key AQVN-key") in stub.metadata[0]
    assert ("x-folder-id", "b1folder") in stub.metadata[0]
    await stream.close()


async def test_stream_reopens_after_server_ends_it() -> None:
    stub = _Stub()
    stream = YandexSttStream(credential="b1folder:AQVN-key", stub=stub)
    await stream.open(language="ru")

    await stream.send_audio(b"\x00" * 3200)
    await stream.finalize()
    await asyncio.wait_for(_collect(stream, 1), timeout=1)
    await asyncio.sleep(0.01)  # let the ended stream's reader finish
    await stream.send_audio(b"\x00" * 3200)
    await stream.finalize()
    second = await asyncio.wait_for(_collect(stream, 1), timeout=1)

    assert second == [SttResult("привет мир", True)]
    assert len(stub.calls) == 2
    await stream.close()


async def test_three_consecutive_failures_make_results_raise() -> None:
    stub = _Stub(failures=3)
    stream = YandexSttStream(credential="b1folder:AQVN-key", stub=stub)
    await stream.open(language="ru")

    with pytest.raises(SttUnavailable):
        for _ in range(3):
            await stream.send_audio(b"\x00" * 3200)
            await stream.finalize()
            await asyncio.sleep(0.01)
        await asyncio.wait_for(_collect(stream, 1), timeout=1)
    await stream.close()


async def test_billing_rounds_each_stream_up_to_fifteen_seconds() -> None:
    stub = _Stub()
    stream = YandexSttStream(credential="b1folder:AQVN-key", stub=stub)
    await stream.open(language="ru")

    await stream.send_audio(b"\x00" * 32000 * 2)  # 2 s
    await stream.finalize()
    await asyncio.wait_for(_collect(stream, 1), timeout=1)
    await stream.close()

    assert stream.billed_seconds == 15
