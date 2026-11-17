"""Unit tests: outbound agent audio is sent at playback speed, a short lead ahead."""

from __future__ import annotations

import asyncio

from assemblix_api.realtime.paced_audio import PacedAudioSender

_RATE = 16000
_CHUNK_SEC = 0.5
_CHUNK = b"\x00" * int(_RATE * 2 * _CHUNK_SEC)


class _FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


async def _settle() -> None:
    for _ in range(200):
        await asyncio.sleep(0)


def _sender(sent: list[tuple[float, bytes]], fake: _FakeTime) -> PacedAudioSender:
    async def send(pcm: bytes) -> None:
        sent.append((fake.now, pcm))

    return PacedAudioSender(
        send, sample_rate=_RATE, lead_sec=1.5, clock=fake.clock, sleep=fake.sleep
    )


async def test_a_long_reply_is_never_sent_more_than_the_lead_ahead() -> None:
    """A 10 s reply pushed at once goes out in step with playback."""
    # Arrange
    fake, sent = _FakeTime(), []
    sender = _sender(sent, fake)

    # Act
    for _ in range(20):
        sender.push(_CHUNK)
    await _settle()
    await sender.aclose()

    # Assert — everything arrives, and audio sent by time t never exceeds t + lead
    assert len(sent) == 20
    for index, (at, _pcm) in enumerate(sent):
        audio_sent_after = (index + 1) * _CHUNK_SEC
        assert audio_sent_after <= at + 1.5 + _CHUNK_SEC


async def test_drop_discards_audio_not_yet_sent() -> None:
    """A barge-in drops the queued tail; the next reply starts at once."""
    # Arrange
    fake, sent = _FakeTime(), []
    sender = _sender(sent, fake)
    for _ in range(20):
        sender.push(_CHUNK)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    # Act
    sender.drop()
    await _settle()
    sent_before_next = len(sent)
    started = fake.now
    sender.push(b"\x01" * len(_CHUNK))
    await _settle()
    await sender.aclose()

    # Assert
    assert sent_before_next < 20
    assert sent[-1] == (started, b"\x01" * len(_CHUNK))
