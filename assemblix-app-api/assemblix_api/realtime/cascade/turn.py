"""Turn-taking for cascade calls: VAD gating plus Smart Turn end-of-turn.

Time is counted in audio frames rather than wall-clock, so behaviour is
deterministic and independent of how the network batches audio.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import numpy as np

from assemblix_api.realtime.cascade.models import SAMPLE_RATE, VadModel
from assemblix_api.schemas.voice_agent import TurnConfig

_SPEECH_THRESHOLD = 0.5
_ONSET_FRAMES = 2
_WINDOW_SECONDS = 8

Completion = Callable[[np.ndarray], Awaitable[float]]


@dataclass(frozen=True)
class SpeechStart:
    pass


@dataclass(frozen=True)
class EndOfTurn:
    eou_ms: int


@dataclass
class TurnUpdate:
    stt_audio: bytes = b""
    signals: list[SpeechStart | EndOfTurn] = field(default_factory=list)


class TurnDetector:
    def __init__(self, *, vad: VadModel, completion: Completion, config: TurnConfig) -> None:
        self._vad = vad
        self._completion = completion
        self._config = config
        self._frame_bytes = vad.frame_samples * 2
        self._frame_ms = vad.frame_samples * 1000 // SAMPLE_RATE
        self._buffer = b""
        self._preroll: deque[bytes] = deque(maxlen=max(1, config.preroll_ms // self._frame_ms))
        self._onset: list[bytes] = []
        self._turn_audio: deque[bytes] = deque(
            maxlen=_WINDOW_SECONDS * SAMPLE_RATE // vad.frame_samples
        )
        self._in_turn = False
        self._silence_ms = 0
        self._asked = False

    async def push(self, pcm: bytes) -> TurnUpdate:
        update = TurnUpdate()
        self._buffer += pcm
        while len(self._buffer) >= self._frame_bytes:
            frame = self._buffer[: self._frame_bytes]
            self._buffer = self._buffer[self._frame_bytes :]
            await self._on_frame(frame, update)
        return update

    async def _on_frame(self, frame: bytes, update: TurnUpdate) -> None:
        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0
        is_speech = self._vad.speech_probability(samples) >= _SPEECH_THRESHOLD

        if not self._in_turn:
            if not is_speech:
                self._preroll.extend(self._onset)
                self._onset.clear()
                self._preroll.append(frame)
                return
            self._onset.append(frame)
            if len(self._onset) < _ONSET_FRAMES:
                return
            head = [*self._preroll, *self._onset]
            self._preroll.clear()
            self._onset.clear()
            self._turn_audio.clear()
            self._turn_audio.extend(head)
            self._in_turn = True
            self._silence_ms = 0
            self._asked = False
            update.signals.append(SpeechStart())
            update.stt_audio += b"".join(head)
            return

        update.stt_audio += frame
        self._turn_audio.append(frame)
        if is_speech:
            self._silence_ms = 0
            self._asked = False
            return

        self._silence_ms += self._frame_ms
        if (
            self._config.smart_turn
            and not self._asked
            and self._silence_ms >= self._config.min_silence_ms
        ):
            self._asked = True
            pause_frames = self._silence_ms // self._frame_ms
            speech = list(self._turn_audio)[: len(self._turn_audio) - pause_frames]
            audio = np.frombuffer(b"".join(speech), dtype=np.int16)
            probability = await self._completion(audio.astype(np.float32) / 32768.0)
            if probability >= self._config.smart_turn_threshold:
                self._end(update)
                return
        if self._silence_ms >= self._config.max_silence_ms:
            self._end(update)

    def _end(self, update: TurnUpdate) -> None:
        update.signals.append(EndOfTurn(eou_ms=self._silence_ms))
        self._in_turn = False
        self._silence_ms = 0
        self._asked = False
