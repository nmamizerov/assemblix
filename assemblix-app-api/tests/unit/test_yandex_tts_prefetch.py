"""Yandex realtime TTS: segments are synthesized ahead and played strictly in order.

The fake stub's latency is proportional to the text length, like SpeechKit, which
returns a segment's audio only after synthesizing most of it.
"""

import asyncio
import re
import time

from yandex.cloud.ai.tts.v3 import tts_pb2

from assemblix_api.external.voice.streaming_tts.yandex import Segmenter, YandexRealtimeSession

_CHUNKS = 3


class _LatencyCall:
    def __init__(self, stub, index, text):
        self._stub = stub
        self._index = index
        self._text = text
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    async def __aiter__(self):
        await asyncio.sleep(len(self._text) * self._stub.sec_per_char)
        for chunk in range(_CHUNKS):
            yield tts_pb2.UtteranceSynthesisResponse(
                audio_chunk=tts_pb2.AudioChunk(data=bytes([self._index, chunk]))
            )
            await asyncio.sleep(self._stub.chunk_sec)


class _LatencyStub:
    def __init__(self, *, sec_per_char=0.001, chunk_sec=0.0):
        self.sec_per_char = sec_per_char
        self.chunk_sec = chunk_sec
        self.calls: list[_LatencyCall] = []
        self.texts: list[str] = []
        self.started_at: list[float] = []

    def UtteranceSynthesis(self, request, metadata=None):
        call = _LatencyCall(self, len(self.calls), request.text)
        self.calls.append(call)
        self.texts.append(request.text)
        self.started_at.append(time.monotonic())
        return call


def _session(stub, on_audio, mode="utterance"):
    return YandexRealtimeSession(
        credential="b1folder:AQVN-key",
        voice_id="alena",
        model="yandex-tts-v3",
        on_audio=on_audio,
        mode=mode,
        stub=stub,
    )


def _words(text: str) -> list[str]:
    return text.split()


_REPLY = (
    "Конечно. Сейчас я эйч-ар бизнес-партнёр корпоративного блока, работаю в компании "
    "с сентября две тысячи девятнадцатого года. Сопровождаю подразделения. Отвечаю на вопросы."
)


async def test_later_segments_are_requested_before_the_first_finished_playing():
    # Arrange
    heard: list[tuple[bytes, float]] = []

    async def on_audio(pcm, _alignment):
        heard.append((pcm, time.monotonic()))

    stub = _LatencyStub(chunk_sec=0.02)
    session = _session(stub, on_audio)
    await session.open()

    # Act
    await session.send_text(_REPLY)
    await session.flush_and_close()

    # Assert
    first_done = max(at for pcm, at in heard if pcm[0] == 0)
    assert len(stub.started_at) >= 3
    assert stub.started_at[1] < first_done
    assert stub.started_at[2] < first_done


async def test_audio_is_forwarded_in_segment_order_when_a_later_one_finishes_first():
    # Arrange
    received: list[bytes] = []

    async def on_audio(pcm, _alignment):
        received.append(pcm)

    stub = _LatencyStub(sec_per_char=0.002)
    session = _session(stub, on_audio)
    await session.open()

    # Act
    await session.send_text("Это довольно длинная первая фраза ответа агента. Да. Нет.")
    await session.flush_and_close()

    # Assert
    assert stub.texts == ["Это довольно длинная первая фраза ответа агента.", "Да.", "Нет."]
    assert received == [bytes([index, chunk]) for index in range(3) for chunk in range(_CHUNKS)]


async def test_aclose_cancels_every_request_in_flight_and_stops_forwarding():
    # Arrange
    received: list[bytes] = []
    first = asyncio.Event()

    async def on_audio(pcm, _alignment):
        received.append(pcm)
        first.set()

    stub = _LatencyStub(sec_per_char=0.0, chunk_sec=0.05)
    session = _session(stub, on_audio)
    await session.open()
    await session.send_text("Первое. Второе. Третье. Четвёртое.")
    await first.wait()

    # Act
    await session.aclose()
    heard = len(received)
    await asyncio.sleep(0.2)

    # Assert
    assert len(stub.calls) == 3
    assert all(call.cancelled for call in stub.calls)
    assert len(received) == heard
    assert session._worker is not None and session._worker.done()


async def test_billing_counts_every_character_sent():
    # Arrange
    async def on_audio(_pcm, _alignment):
        return None

    parts = ["Конечно. ", "Сейчас я эйч-ар ", "бизнес-партнёр, ", "работаю давно.", " Хвост"]
    session = _session(_LatencyStub(sec_per_char=0.0), on_audio, mode="chunk")
    await session.open()

    # Act
    for part in parts:
        await session.send_text(part)
    chars = await session.flush_and_close()

    # Assert
    assert chars == sum(len(part) for part in parts)


def test_first_segment_ends_at_the_first_clause_after_twenty_chars():
    # Arrange
    segmenter = Segmenter(pack=True)

    # Act
    segments = segmenter.feed(
        "Сейчас я эйч-ар бизнес-партнёр корпоративного блока, работаю в компании давно"
    )

    # Assert
    assert segments == ["Сейчас я эйч-ар бизнес-партнёр корпоративного блока,"]


def test_first_segment_without_punctuation_is_cut_at_a_space_within_eighty_chars():
    # Arrange
    text = "слово " * 30
    segmenter = Segmenter(pack=True)

    # Act
    segments = segmenter.feed(text)

    # Assert
    assert len(segments[0]) <= 80
    assert set(_words(segments[0])) == {"слово"}


def test_segments_ramp_up_and_never_split_a_word():
    # Arrange
    long_sentence = (
        "Я сопровождаю подразделения корпоративного блока, помогаю руководителям с наймом "
        "и развитием команд, а также отвечаю за адаптацию новых сотрудников в компании."
    )
    text = "Конечно. " + long_sentence + " " + "Это короткое предложение. " * 12 + "Хвост"
    segmenter = Segmenter(pack=True)

    # Act
    segments = segmenter.feed(text) + segmenter.flush()

    # Assert
    assert segments[0] == "Конечно."
    assert len(segments[1]) <= 140
    assert all(len(segment) <= 250 for segment in segments)
    assert any(len(segment) > 140 for segment in segments[2:])  # packed after the ramp
    assert segments[-1].endswith("Хвост")
    assert [w for s in segments for w in _words(s)] == _words(text)


def test_utterance_mode_splits_a_long_sentence_at_a_clause_near_the_middle():
    # Arrange
    long_sentence = (
        "Я сопровождаю подразделения корпоративного блока и помогаю руководителям с наймом, "
        "развитием команд и адаптацией новых сотрудников во всех региональных офисах компании."
    )
    segmenter = Segmenter(pack=False)
    segmenter.feed("Конечно. Второй сегмент ответа. ")

    # Act
    segments = segmenter.feed(long_sentence + " ")

    # Assert
    assert len(long_sentence) > 140
    assert len(segments) == 2
    assert segments[0].endswith("наймом,")
    assert all(len(segment) <= 140 for segment in segments)
    assert " ".join(segments) == long_sentence


def test_unfinished_text_waits_for_more_and_flush_sends_the_remainder():
    # Arrange
    segmenter = Segmenter(pack=True)

    # Act
    held = segmenter.feed("Привет")
    flushed = segmenter.flush()

    # Assert
    assert held == []
    assert flushed == ["Привет"]


def test_hyphenated_words_and_decimals_are_not_boundaries():
    # Arrange
    segmenter = Segmenter(pack=True)

    # Act
    segments = (
        segmenter.feed("Ставка 2,5 процента для эйч-ар отдела — это много, ") + segmenter.flush()
    )

    # Assert
    assert segments[0] == "Ставка 2,5 процента для эйч-ар отдела —"
    assert not any(re.search(r"\w-$|^-\w", s) for s in segments)


async def test_stream_mode_forces_synthesis_at_every_segment_boundary():
    # Arrange
    sent: list[tts_pb2.StreamSynthesisRequest] = []

    class _StreamStub:
        def StreamSynthesis(self, requests, metadata=None):
            async def responses():
                async for request in requests:
                    sent.append(request)
                    if request.HasField("force_synthesis"):
                        yield tts_pb2.StreamSynthesisResponse(
                            audio_chunk=tts_pb2.AudioChunk(data=b"\x01")
                        )

            return responses()

    async def on_audio(_pcm, _alignment):
        return None

    session = _session(_StreamStub(), on_audio, mode="stream")
    await session.open()

    # Act
    await session.send_text("Конечно. Сейчас я эйч-ар бизнес-партнёр корпоративного блока, ")
    await session.send_text("работаю давно.")
    await session.flush_and_close()

    # Assert
    kinds = [request.WhichOneof("Event") for request in sent]
    texts = [r.synthesis_input.text for r in sent if r.HasField("synthesis_input")]
    assert kinds[0] == "options"
    assert texts == [
        "Конечно.",
        "Сейчас я эйч-ар бизнес-партнёр корпоративного блока, работаю давно.",
    ]
    assert kinds[1:] == ["synthesis_input", "force_synthesis"] * 2
