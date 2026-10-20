"""PCM resampling to the 24 kHz mono s16le avatars expect."""

from __future__ import annotations

from typing import Any

AVATAR_SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2


class Resampler:
    def __init__(self) -> None:
        self._resampler: Any = None
        self._rate: int | None = None

    def push(self, pcm: bytes, sample_rate: int) -> bytes:
        if sample_rate == AVATAR_SAMPLE_RATE:
            return pcm
        from livekit import rtc

        if self._resampler is None or self._rate != sample_rate:
            self._resampler = rtc.AudioResampler(sample_rate, AVATAR_SAMPLE_RATE, num_channels=1)
            self._rate = sample_rate
        frame = rtc.AudioFrame(pcm, sample_rate, 1, len(pcm) // BYTES_PER_SAMPLE)
        return b"".join(bytes(out.data) for out in self._resampler.push(frame))

    def flush(self) -> bytes:
        if self._resampler is None:
            return b""
        tail = b"".join(bytes(out.data) for out in self._resampler.flush())
        self._resampler = None
        return tail

    def reset(self) -> None:
        self._resampler = None
