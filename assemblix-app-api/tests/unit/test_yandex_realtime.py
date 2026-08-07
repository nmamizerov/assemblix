"""Happy-flow coverage for the Yandex SpeechKit v3 realtime TTS provider.

Uses an injected fake gRPC stub (no network): feed two sentences, assert both are
synthesized whole and their PCM is forwarded to ``on_audio`` in order.
"""

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
