"""Outbound agent audio, sent at playback speed instead of in one burst.

A TTS reply is synthesized far faster than it plays: a 40-second answer can be ready
in half a second. Written to the socket at once, it queues every later frame —
including the server's keepalive ping — behind tens of seconds of audio. On a link
barely faster than real time the pong then misses its deadline and the call is cut.
Pacing keeps only a short lead over playback in flight; the rest waits here, where a
barge-in can still drop it.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import deque
from collections.abc import Awaitable, Callable

_BYTES_PER_SAMPLE = 2
# How far sent audio may run ahead of the caller's playback: enough to ride out
# network jitter, small enough that control frames never wait long behind it.
LEAD_SEC = 1.5


class PacedAudioSender:
    def __init__(
        self,
        send: Callable[[bytes], Awaitable[None]],
        *,
        sample_rate: int,
        lead_sec: float = LEAD_SEC,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._send = send
        self._bytes_per_sec = sample_rate * _BYTES_PER_SAMPLE
        self._lead = lead_sec
        self._clock = clock
        self._sleep = sleep
        self._chunks: deque[bytes] = deque()
        self._wake = asyncio.Event()
        # When the caller finishes playing everything sent so far.
        self._play_end = 0.0
        self._task: asyncio.Task[None] | None = None

    def push(self, pcm: bytes) -> None:
        self._chunks.append(pcm)
        self._wake.set()
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    def drop(self) -> None:
        """Forget audio not yet sent; the caller has flushed what it was playing."""
        self._chunks.clear()
        self._play_end = 0.0

    async def aclose(self) -> None:
        self._chunks.clear()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        while True:
            if not self._chunks:
                self._wake.clear()
                await self._wake.wait()
                continue
            now = self._clock()
            ahead = self._play_end - now
            if ahead > self._lead:
                # Re-checked after the wait: a barge-in may have dropped the queue.
                await self._sleep(ahead - self._lead)
                continue
            pcm = self._chunks.popleft()
            self._play_end = max(self._play_end, now) + len(pcm) / self._bytes_per_sec
            try:
                await self._send(pcm)
            except Exception:
                # The socket is gone; the receive side ends the call.
                self._chunks.clear()
                return
