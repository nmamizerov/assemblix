"""Feed a LiveAvatar LITE session over its session WebSocket.

LiveAvatar joins our LiveKit room for video but takes the agent's voice as JSON
commands on a per-session socket: ``agent.speak`` chunks of base64 PCM (24 kHz mono
s16le), ``agent.speak_end`` to seal an utterance, ``agent.interrupt`` to barge in.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import structlog

from assemblix_api.external.avatar.errors import AvatarUnavailable
from assemblix_api.realtime.livekit.resample import (
    AVATAR_SAMPLE_RATE,
    BYTES_PER_SAMPLE,
    Resampler,
)

logger = structlog.get_logger(__name__)

# The first chunk of each utterance trades lip-sync smoothness for latency; the
# LiveKit plugin uses 600 ms. Tune against video_starvation warnings.
FIRST_CHUNK_MS = 600

_BYTES_PER_MS = AVATAR_SAMPLE_RATE * BYTES_PER_SAMPLE // 1000


async def connect_socket(url: str) -> Any:
    import websockets

    return await websockets.connect(url, max_size=None)


class LiveAvatarSocketOutput:
    def __init__(
        self,
        ws: Any,
        *,
        first_chunk_ms: int = FIRST_CHUNK_MS,
        chunk_ms: int = 1000,
        keepalive_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ws = ws
        self._first_chunk_bytes = first_chunk_ms * _BYTES_PER_MS
        self._chunk_bytes = chunk_ms * _BYTES_PER_MS
        self._keepalive_seconds = keepalive_seconds
        self._clock = clock
        self._resampler = Resampler()
        self._buffer = bytearray()
        self._utterance_id: str | None = None  # set while an utterance is open
        self._last_utterance_id: str | None = None
        self._chunks_sent = 0
        self._sent_ms = 0.0
        self._started_at = 0.0
        self._last_send = clock()
        self._connected = asyncio.Event()
        self._closed = False
        self._tasks: list[asyncio.Task] = []
        # True from the first chunk sent until the avatar reports it finished.
        self.playing = False

    async def wait_connected(self) -> None:
        if not self._tasks:
            self._tasks = [
                asyncio.create_task(self._read()),
                asyncio.create_task(self._keepalive()),
            ]
        await self._connected.wait()
        if self._closed:
            raise AvatarUnavailable("LiveAvatar closed the session socket before connecting")

    async def push(self, pcm: bytes, sample_rate: int) -> None:
        self._raise_if_closed()
        self._buffer += self._resampler.push(pcm, sample_rate)
        if self._utterance_id is None:
            self._utterance_id = uuid4().hex
            self._chunks_sent = 0
        while len(self._buffer) >= self._next_chunk_bytes():
            size = self._next_chunk_bytes()
            chunk, self._buffer = bytes(self._buffer[:size]), self._buffer[size:]
            await self._speak(chunk)

    async def end_utterance(self) -> None:
        self._raise_if_closed()
        if self._utterance_id is None:
            return
        tail = bytes(self._buffer) + self._resampler.flush()
        self._buffer = bytearray()
        if tail:
            await self._speak(tail)
        if self._chunks_sent:
            await self._send({"type": "agent.speak_end"})
        self._utterance_id = None

    async def interrupt(self) -> int | None:
        if self._utterance_id is None and not self.playing:
            return None
        self._buffer = bytearray()
        self._resampler.reset()
        self._utterance_id = None
        if not self.playing:
            return 0
        heard_ms = int(min(self._sent_ms, (self._clock() - self._started_at) * 1000))
        self.playing = False
        if not self._closed:
            await self._send({"type": "agent.interrupt"})
        return heard_ms

    async def aclose(self) -> None:
        self._closed = True
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        with contextlib.suppress(Exception):
            await self._ws.close()

    def _next_chunk_bytes(self) -> int:
        return self._chunk_bytes if self._chunks_sent else self._first_chunk_bytes

    async def _speak(self, chunk: bytes) -> None:
        message: dict[str, Any] = {
            "type": "agent.speak",
            "audio": base64.b64encode(chunk).decode(),
        }
        if self._chunks_sent == 0:
            message["event_id"] = self._utterance_id
            self._last_utterance_id = self._utterance_id
            if not self.playing:
                self._started_at = self._clock()
                self._sent_ms = 0.0
            self.playing = True
        await self._send(message)
        self._chunks_sent += 1
        self._sent_ms += len(chunk) / _BYTES_PER_MS

    async def _send(self, message: dict[str, Any]) -> None:
        try:
            await self._ws.send(json.dumps(message))
        except Exception as exc:
            self._closed = True
            raise AvatarUnavailable("LiveAvatar session socket failed") from exc
        self._last_send = self._clock()

    def _raise_if_closed(self) -> None:
        if self._closed:
            raise AvatarUnavailable("LiveAvatar ended the session")

    async def _read(self) -> None:
        try:
            async for raw in self._ws:
                self._on_event(json.loads(raw))
        except Exception as exc:  # noqa: BLE001 — any socket failure ends the avatar.
            logger.warning("liveavatar.socket_failed", error=str(exc))
        finally:
            self._closed = True
            self._connected.set()

    def _on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "session.state_updated":
            if event.get("state") == "connected":
                self._connected.set()
        elif kind == "agent.speak_ended":
            if self._utterance_id is None and event.get("source_event_id") == (
                self._last_utterance_id
            ):
                self.playing = False
        elif kind in ("error", "warning"):
            logger.warning("liveavatar.event", type=kind, detail=event.get(kind))

    async def _keepalive(self) -> None:
        while not self._closed:
            await asyncio.sleep(self._keepalive_seconds)
            idle = self._clock() - self._last_send
            if self._connected.is_set() and not self._closed and idle >= self._keepalive_seconds:
                with contextlib.suppress(AvatarUnavailable):
                    await self._send({"type": "session.keep_alive"})
