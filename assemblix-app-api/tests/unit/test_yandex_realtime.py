"""Happy-flow coverage for the Yandex SpeechKit v3 realtime TTS provider.

Uses an injected fake gRPC stub (no network): feed two sentences, assert both are
synthesized whole and their PCM is forwarded to ``on_audio`` in order.
"""

import asyncio

import pytest
from yandex.cloud.ai.tts.v3 import tts_pb2

from assemblix_api.external.voice.streaming_tts.yandex import YandexRealtimeSession


class _FakeCall:
    """Async-iterable UnaryStream call returning two PCM chunks."""

    def __init__(self):
        self._chunks = [b"\x01\x02", b"\x03\x04"]

    async def __aiter__(self):
        for data in self._chunks:
            yield tts_pb2.UtteranceSynthesisResponse(audio_chunk=tts_pb2.AudioChunk(data=data))


class _FakeStub:
    def __init__(self):
        self.calls = []

    def UtteranceSynthesis(self, request, metadata=None):
        self.calls.append((request, metadata))
        return _FakeCall()


@pytest.mark.asyncio
async def test_yandex_realtime_utterance_happy_flow():
    # Arrange
    received: list[bytes] = []

    async def on_audio(pcm, _alignment):
        received.append(pcm)

    stub = _FakeStub()
    session = YandexRealtimeSession(
        credential="b1folder:AQVN-key",
        voice_id="alena",
        model="yandex-tts-v3",
        on_audio=on_audio,
        mode="utterance",
        stub=stub,
    )

    # Act
    await session.open()
    await session.send_text("Привет. ")
    await session.send_text("Как дела?")
    chars = await session.flush_and_close()

    # Assert — both sentences synthesized whole, PCM forwarded in order.
    assert chars == len("Привет. ") + len("Как дела?")
    assert [req.text for req, _ in stub.calls] == ["Привет.", "Как дела?"]
    assert received == [b"\x01\x02", b"\x03\x04", b"\x01\x02", b"\x03\x04"]

    # Request shape: raw 16 kHz LINEAR16 PCM, voice hint, Api-Key + folder metadata.
    req, meta = stub.calls[0]
    assert req.output_audio_spec.raw_audio.audio_encoding == tts_pb2.RawAudio.LINEAR16_PCM
    assert req.output_audio_spec.raw_audio.sample_rate_hertz == 16000
    assert req.hints[0].voice == "alena"
    assert ("authorization", "Api-Key AQVN-key") in meta
    assert ("x-folder-id", "b1folder") in meta


@pytest.mark.asyncio
async def test_chunk_mode_sends_first_sentence_then_packs_the_rest():
    async def on_audio(_pcm, _alignment):
        return None

    stub = _FakeStub()
    session = YandexRealtimeSession(
        credential="b1folder:AQVN-key",
        voice_id="alena",
        model="yandex-tts-v3-chunk",
        on_audio=on_audio,
        mode="chunk",
        stub=stub,
    )
    long_sentence = "Это довольно длинное предложение для проверки упаковки текста. "

    await session.open()
    await session.send_text("Здравствуйте! ")
    for _ in range(5):
        await session.send_text(long_sentence)
    await session.send_text("Хвост")
    await session.flush_and_close()

    texts = [req.text for req, _ in stub.calls]
    assert texts[0] == "Здравствуйте!"
    assert all(len(t) <= 250 for t in texts[1:-1])
    assert texts[-1].endswith("Хвост")
    assert len(texts) < 7  # packed, not one request per sentence


@pytest.mark.asyncio
async def test_shared_channel_is_not_closed_by_the_session():
    class _Channel:
        closed = False

        async def close(self):
            self.closed = True

    async def on_audio(_pcm, _alignment):
        return None

    channel = _Channel()
    session = YandexRealtimeSession(
        credential="b1folder:AQVN-key",
        voice_id="alena",
        model="yandex-tts-v3",
        on_audio=on_audio,
        stub=_FakeStub(),
        channel=channel,
    )
    await session.open()
    await session.flush_and_close()

    assert channel.closed is False


class _SlowCall:
    """An in-flight synthesis that keeps producing audio until cancelled."""

    def __init__(self, started):
        self._started = started
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    async def __aiter__(self):
        for _ in range(100):
            self._started.set()
            await asyncio.sleep(0.01)
            yield tts_pb2.UtteranceSynthesisResponse(audio_chunk=tts_pb2.AudioChunk(data=b"\x01"))


class _SlowStub:
    def __init__(self):
        self.started = asyncio.Event()
        self.calls: list[_SlowCall] = []

    def UtteranceSynthesis(self, request, metadata=None):
        call = _SlowCall(self.started)
        self.calls.append(call)
        return call


@pytest.mark.asyncio
async def test_aclose_on_a_shared_channel_stops_the_synthesis_in_flight():
    received: list[bytes] = []

    async def on_audio(pcm, _alignment):
        received.append(pcm)

    class _Channel:
        closed = False

        async def close(self):
            self.closed = True

    channel = _Channel()
    stub = _SlowStub()
    session = YandexRealtimeSession(
        credential="b1folder:AQVN-key",
        voice_id="alena",
        model="yandex-tts-v3",
        on_audio=on_audio,
        stub=stub,
        channel=channel,
    )
    await session.open()
    await session.send_text("Первое. Второе. ")
    await stub.started.wait()

    await session.aclose()
    heard = len(received)
    started = len(stub.calls)
    await session.send_text("Третье. ")
    await asyncio.sleep(0.05)

    assert session._worker is not None and session._worker.done()
    assert all(call.cancelled for call in stub.calls)
    assert len(received) == heard
    assert len(stub.calls) == started
    assert channel.closed is False
