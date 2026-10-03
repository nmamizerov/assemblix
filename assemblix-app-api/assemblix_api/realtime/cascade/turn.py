"""Turn-taking for cascade calls: VAD gating plus Smart Turn end-of-turn.

Time is counted in audio frames rather than wall-clock, so behaviour is
deterministic and independent of how the network batches audio.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import numpy as np

from assemblix_api.realtime.cascade.models import SAMPLE_RATE, VadModel
from assemblix_api.schemas.voice_agent import TurnConfig

_SPEECH_THRESHOLD = 0.5
_ONSET_FRAMES = 2
_WINDOW_SECONDS = 8
# Smart Turn is re-asked during a long pause, demanding less certainty the longer it lasts.
_REASK_MS = 150
_MAX_ASKS_PER_PAUSE = 10
_THRESHOLD_FLOOR = 0.15

Completion = Callable[[np.ndarray], Awaitable[float]]


@dataclass(frozen=True)
class SpeechStart:
    pass


@dataclass(frozen=True)
class PauseStart:
    """Tentative end of turn: the pause reached ``min_silence_ms``, Smart Turn is being asked."""


@dataclass(frozen=True)
class PauseCancelled:
    """Speech resumed after a ``PauseStart`` — the same turn goes on."""


@dataclass(frozen=True)
class EndOfTurn:
    eou_ms: int
    smart_turn_prob: float | None = None
    smart_turn_asks: int = 0


Signal = SpeechStart | PauseStart | PauseCancelled | EndOfTurn


@dataclass
class TurnUpdate:
    stt_audio: bytes = b""
    signals: list[Signal] = field(default_factory=list)
    # A Smart Turn ask is pending behind a PauseStart: push(b"") again to settle it.
    more: bool = False


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
        self._ask: asyncio.Future[float] | None = None
        self._ask_silence_ms = 0
        self._next_ask_ms = config.min_silence_ms
        self._pause_asks = 0
        self._paused = False
        self._turn_asks = 0
        self._last_prob: float | None = None

    async def push(self, pcm: bytes) -> TurnUpdate:
        update = TurnUpdate()
        self._buffer += pcm
        if self._ask is not None:
            await self._settle_ask(update)
        while len(self._buffer) >= self._frame_bytes:
            frame = self._buffer[: self._frame_bytes]
            self._buffer = self._buffer[self._frame_bytes :]
            paused = self._paused
            self._on_frame(frame, update)
            if self._ask is None:
                continue
            if self._paused and not paused:
                update.more = True
                return update
            await self._settle_ask(update)
        return update

    def _on_frame(self, frame: bytes, update: TurnUpdate) -> None:
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
            self._turn_asks = 0
            self._last_prob = None
            self._reset_pause()
            update.signals.append(SpeechStart())
            update.stt_audio += b"".join(head)
            return

        update.stt_audio += frame
        self._turn_audio.append(frame)
        if is_speech:
            if self._paused:
                update.signals.append(PauseCancelled())
            self._reset_pause()
            return

        self._silence_ms += self._frame_ms
        if self._silence_ms >= self._config.max_silence_ms:
            self._end(update)
            return
        if (
            self._config.smart_turn
            and self._silence_ms >= self._next_ask_ms
            and self._pause_asks < _MAX_ASKS_PER_PAUSE
        ):
            self._start_ask(update)

    def _start_ask(self, update: TurnUpdate) -> None:
        if self._config.speculative and not self._paused:
            self._paused = True
            update.signals.append(PauseStart())
        pause_frames = self._silence_ms // self._frame_ms
        speech = list(self._turn_audio)[: len(self._turn_audio) - pause_frames]
        audio = np.frombuffer(b"".join(speech), dtype=np.int16).astype(np.float32) / 32768.0
        self._ask_silence_ms = self._silence_ms
        self._next_ask_ms = self._silence_ms + _REASK_MS
        self._pause_asks += 1
        self._turn_asks += 1
        self._ask = asyncio.ensure_future(self._completion(audio))

    async def _settle_ask(self, update: TurnUpdate) -> None:
        ask, self._ask = self._ask, None
        if ask is None:
            return
        probability = await ask
        self._last_prob = probability
        if probability >= self._threshold(self._ask_silence_ms):
            self._end(update)

    def _threshold(self, silence_ms: int) -> float:
        """Linear decay from ``smart_turn_threshold`` at min silence to a floor at max."""
        config = self._config
        start = config.smart_turn_threshold
        floor = min(_THRESHOLD_FLOOR, start)
        span = config.max_silence_ms - config.min_silence_ms
        if span <= 0:
            return start
        progress = min(1.0, max(0.0, (silence_ms - config.min_silence_ms) / span))
        return start - (start - floor) * progress

    def _reset_pause(self) -> None:
        self._silence_ms = 0
        self._next_ask_ms = self._config.min_silence_ms
        self._pause_asks = 0
        self._paused = False

    def _end(self, update: TurnUpdate) -> None:
        update.signals.append(
            EndOfTurn(
                eou_ms=self._silence_ms,
                smart_turn_prob=self._last_prob,
                smart_turn_asks=self._turn_asks,
            )
        )
        self._in_turn = False
        self._reset_pause()
