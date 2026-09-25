"""Feed an avatar participant PCM over LiveKit's data-stream avatar protocol.

The same protocol LiveKit's avatar plugins speak: one ``lk.audio_stream`` byte
stream per utterance (closing it ends the utterance), ``lk.clear_buffer`` to
barge in, ``lk.playback_finished`` back when the avatar stopped talking.
Vendors don't reliably send ``lk.playback_started``, so nothing depends on it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)

AVATAR_SAMPLE_RATE = 24000
AUDIO_STREAM_TOPIC = "lk.audio_stream"
RPC_CLEAR_BUFFER = "lk.clear_buffer"
RPC_PLAYBACK_FINISHED = "lk.playback_finished"
RPC_PLAYBACK_STARTED = "lk.playback_started"

_BYTES_PER_SAMPLE = 2


class AvatarAudioOutput:
    def __init__(
        self,
        participant: Any,
        *,
        destination: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._participant = participant
        self._destination = destination
        self._clock = clock
        self._writer: Any = None
        self._resampler: Any = None
        self._resampler_rate: int | None = None
        self._sent_ms = 0.0
        self._started_at = 0.0
        # True from the first chunk until the avatar reports it stopped: providers
        # generate faster than realtime, so "generation ended" is not "silent".
        self.playing = False
        participant.register_rpc_method(RPC_PLAYBACK_FINISHED, self._on_playback_finished)
        participant.register_rpc_method(RPC_PLAYBACK_STARTED, lambda _data: "ok")

    async def push(self, pcm: bytes, sample_rate: int) -> None:
        data = self._to_avatar_rate(pcm, sample_rate)
        if self._writer is None:
            self._writer = await self._participant.stream_bytes(
                f"AUDIO_{uuid4().hex[:12]}",
                topic=AUDIO_STREAM_TOPIC,
                destination_identities=[self._destination],
                attributes={"sample_rate": str(AVATAR_SAMPLE_RATE), "num_channels": "1"},
            )
            if not self.playing:
                self._started_at = self._clock()
                self._sent_ms = 0.0
            self.playing = True
        if data:
            await self._writer.write(data)
            self._sent_ms += len(data) / _BYTES_PER_SAMPLE / AVATAR_SAMPLE_RATE * 1000

    async def end_utterance(self) -> None:
        tail = self._flush_resampler()
        if self._writer is not None:
            if tail:
                await self._writer.write(tail)
                self._sent_ms += len(tail) / _BYTES_PER_SAMPLE / AVATAR_SAMPLE_RATE * 1000
            writer, self._writer = self._writer, None
            await writer.aclose()

    async def interrupt(self) -> int | None:
        if not self.playing:
            return None
        heard_ms = int(min(self._sent_ms, (self._clock() - self._started_at) * 1000))
        self._resampler = None
        if self._writer is not None:
            writer, self._writer = self._writer, None
            await writer.aclose()
        self.playing = False
        try:
            await self._participant.perform_rpc(
                destination_identity=self._destination, method=RPC_CLEAR_BUFFER, payload=""
            )
        except Exception as exc:  # noqa: BLE001 — a lost RPC must not end the call.
            logger.warning("avatar.clear_buffer_failed", error=str(exc))
        return heard_ms

    def _on_playback_finished(self, _data: Any) -> str:
        if self._writer is None:
            self.playing = False
        return "ok"

    def _to_avatar_rate(self, pcm: bytes, sample_rate: int) -> bytes:
        if sample_rate == AVATAR_SAMPLE_RATE:
            return pcm
        from livekit import rtc

        if self._resampler is None or self._resampler_rate != sample_rate:
            self._resampler = rtc.AudioResampler(sample_rate, AVATAR_SAMPLE_RATE, num_channels=1)
            self._resampler_rate = sample_rate
        frame = rtc.AudioFrame(pcm, sample_rate, 1, len(pcm) // _BYTES_PER_SAMPLE)
        return b"".join(bytes(out.data) for out in self._resampler.push(frame))

    def _flush_resampler(self) -> bytes:
        if self._resampler is None:
            return b""
        tail = b"".join(bytes(out.data) for out in self._resampler.flush())
        self._resampler = None
        return tail
