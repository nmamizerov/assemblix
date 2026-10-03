"""Measures how long a synthesized reply stays silent before speech starts."""

from __future__ import annotations

import math
from array import array

# -45 dBFS on int16; frames quieter than this count as silence.
SILENCE_RMS_THRESHOLD = 184
FRAME_MS = 10
MAX_ANALYSIS_MS = 3000


class LeadingSilenceMeter:
    """Feed PCM16 mono chunks; `result_ms` is set once speech starts or the cap is hit."""

    def __init__(self, sample_rate: int) -> None:
        self._frame_samples = sample_rate * FRAME_MS // 1000
        self._carry = array("h")
        self._silent_frames = 0
        self.result_ms: int | None = None

    @property
    def silence_ms(self) -> int:
        return min(self._silent_frames * FRAME_MS, MAX_ANALYSIS_MS)

    def feed(self, pcm: bytes) -> None:
        if self.result_ms is not None:
            return
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) // 2 * 2])
        self._carry.extend(samples)
        size = self._frame_samples
        offset = 0
        while len(self._carry) - offset >= size:
            frame = self._carry[offset : offset + size]
            offset += size
            if math.sqrt(sum(s * s for s in frame) / size) > SILENCE_RMS_THRESHOLD:
                self.result_ms = self.silence_ms
                break
            self._silent_frames += 1
            if self._silent_frames * FRAME_MS >= MAX_ANALYSIS_MS:
                self.result_ms = MAX_ANALYSIS_MS
                break
        self._carry = self._carry[offset:]
