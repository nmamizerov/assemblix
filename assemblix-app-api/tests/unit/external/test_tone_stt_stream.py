import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import pytest
import websockets

from assemblix_api.external.voice.stt_stream import SttResult, SttUnavailable
from assemblix_api.external.voice.stt_stream.tone import Downsampler, ToneSttStream


class _FakeTone:
    """The T-one lock-step protocol: ready → one binary message → (phrases) → ready."""

    def __init__(self, final_phrases: list[str] | None = None, mid_phrase: str | None = None):
        self.final_phrases = final_phrases if final_phrases is not None else ["привет мир"]
        self.mid_phrase = mid_phrase
        self.connections: list[list[bytes]] = []
        self.extra_messages = 0

    async def handler(self, ws: Any) -> None:
        received: list[bytes] = []
        self.connections.append(received)
        while True:
            await ws.send(json.dumps({"event": "ready"}))
            message = await ws.recv()
            received.append(message)
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.01)
                self.extra_messages += 1
            except TimeoutError:
                pass
            if len(message) == 0:
                for text in self.final_phrases:
                    await _send_phrase(ws, text)
                return
            if self.mid_phrase and len(received) == 1:
                await _send_phrase(ws, self.mid_phrase)


async def _send_phrase(ws: Any, text: str) -> None:
    phrase = {"text": text, "start_time": 0.0, "end_time": 1.0}
    await ws.send(json.dumps({"event": "transcript", "phrase": phrase}))


@asynccontextmanager
async def _serve(fake: _FakeTone) -> AsyncIterator[str]:
    async with websockets.serve(fake.handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        yield f"ws://127.0.0.1:{port}/api/ws"


def _pcm(seconds: float, freq: float = 440.0, rate: int = 16000) -> bytes:
    t = np.arange(int(seconds * rate)) / rate
    return (np.sin(2 * np.pi * freq * t) * 8000).astype("<i2").tobytes()


async def _next(results: AsyncIterator[SttResult]) -> SttResult:
    return await asyncio.wait_for(anext(results), timeout=2)


def _tone_power(pcm: bytes, freq: float, rate: int = 8000) -> float:
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    t = np.arange(len(samples)) / rate
    return float(abs(np.dot(samples, np.exp(-2j * np.pi * freq * t))) / len(samples))


def test_downsampling_halves_the_rate_and_filters_aliasing() -> None:
    downsampler = Downsampler()
    source = _pcm(1.0, freq=1000)
    # Odd-sized chunks exercise the filter state and phase across calls.
    out = b"".join(downsampler.process(source[i : i + 642]) for i in range(0, len(source), 642))

    assert len(out) // 2 == pytest.approx(8000, abs=2)
    assert _tone_power(out, 1000) > 3000

    high = Downsampler().process(_pcm(1.0, freq=6000))
    # 6 kHz would alias to 2 kHz without the low-pass.
    assert _tone_power(high, 2000) < 10


async def test_lock_step_audio_and_a_single_final_after_finalize() -> None:
    fake = _FakeTone(final_phrases=["как дела"], mid_phrase="привет")
    async with _serve(fake) as url:
        stream = ToneSttStream(url=url)
        await stream.open(language="ru")
        results = stream.results()
        for _ in range(50):
            await stream.send_audio(_pcm(0.02))
        preview = await _next(results)
        await stream.finalize()
        final = await _next(results)
        await stream.close()

    assert preview == SttResult(text="привет", is_final=False)
    assert final == SttResult(text="привет как дела", is_final=True)
    received = fake.connections[0]
    assert received[-1] == b""
    assert fake.extra_messages == 0
    assert sum(len(m) for m in received) // 2 == pytest.approx(8000, abs=2)
    assert stream.billed_seconds == 0.0
    assert stream.sent_seconds == pytest.approx(1.0, abs=0.01)


async def test_an_utterance_without_phrases_ends_with_an_empty_final() -> None:
    fake = _FakeTone(final_phrases=[])
    async with _serve(fake) as url:
        stream = ToneSttStream(url=url)
        results = stream.results()
        await stream.send_audio(_pcm(0.1))
        await stream.finalize()
        final = await _next(results)
        await stream.close()

    assert final == SttResult(text="", is_final=True)


async def test_next_audio_after_finalize_opens_a_fresh_connection() -> None:
    fake = _FakeTone()
    async with _serve(fake) as url:
        stream = ToneSttStream(url=url)
        results = stream.results()
        for _ in range(2):
            await stream.send_audio(_pcm(0.1))
            await stream.finalize()
            assert (await _next(results)).text == "привет мир"
        await stream.close()

    assert len(fake.connections) == 2


async def test_three_failed_connections_make_the_stream_unavailable() -> None:
    async with websockets.serve(lambda ws: None, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
    stream = ToneSttStream(url=f"ws://127.0.0.1:{port}/api/ws")
    results = stream.results()

    with pytest.raises(SttUnavailable):
        for _ in range(3):
            await stream.send_audio(_pcm(0.02))
            await stream.finalize()
            assert await _next(results) == SttResult(text="", is_final=True)
    await stream.close()


async def test_a_failed_connection_reconnects_on_the_next_audio() -> None:
    fake = _FakeTone()
    async with _serve(fake) as url:
        stream = ToneSttStream(url="ws://127.0.0.1:1/api/ws")
        results = stream.results()
        await stream.send_audio(_pcm(0.02))
        await stream.finalize()
        assert await _next(results) == SttResult(text="", is_final=True)

        stream._url = url
        await stream.send_audio(_pcm(0.1))
        await stream.finalize()
        final = await _next(results)
        await stream.close()

    assert final == SttResult(text="привет мир", is_final=True)
