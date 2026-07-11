"""Sequence-numbered, replayable per-execution event buffer for SSE streaming.

Two backends: an in-memory deque (self-host / inline runs, where the subscriber and the
executor share the process) and a Redis Stream (queued/cross-process runs). Both assign a
monotonic ``seq`` to every event so a late or reconnecting subscriber replays from a cursor.
The buffer is ephemeral — never persisted; dropped after a TTL past completion.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType

TERMINAL_EVENTS = {DebugEventType.EXECUTION_COMPLETE, DebugEventType.ERROR}


class InMemoryStreamBuffer:
    """Retains events per execution and fans out live to any number of subscribers."""

    def __init__(self, max_events: int = 2000, audio_max_chunks: int = 50):
        self._max_events = max_events
        self._audio_max_chunks = audio_max_chunks
        self._events: dict[UUID, deque[DebugEvent]] = {}
        self._audio: dict[UUID, deque[DebugEvent]] = {}
        self._seq: dict[UUID, int] = {}
        self._conds: dict[UUID, asyncio.Condition] = {}

    def open(self, execution_id: UUID) -> None:
        self._events.setdefault(execution_id, deque(maxlen=self._max_events))
        self._audio.setdefault(execution_id, deque(maxlen=self._audio_max_chunks))
        self._seq.setdefault(execution_id, 0)
        self._conds.setdefault(execution_id, asyncio.Condition())

    def is_open(self, execution_id: UUID) -> bool:
        return execution_id in self._events

    async def append(self, execution_id: UUID, event: DebugEvent) -> int:
        if execution_id not in self._events:
            self.open(execution_id)
        self._seq[execution_id] += 1
        event.seq = self._seq[execution_id]
        self._events[execution_id].append(event)
        cond = self._conds[execution_id]
        async with cond:
            cond.notify_all()
        return event.seq

    async def append_transient(self, execution_id: UUID, event: DebugEvent) -> int:
        """Append a live-only event (audio). Shares the seq counter with append() but is
        stored in a small ring that is NOT part of cursor replay, so heavy PCM never evicts
        retained control/text events."""
        if execution_id not in self._events:
            self.open(execution_id)
        self._seq[execution_id] += 1
        event.seq = self._seq[execution_id]
        self._audio[execution_id].append(event)
        cond = self._conds[execution_id]
        async with cond:
            cond.notify_all()
        return event.seq

    async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        if execution_id not in self._events:
            return
        cond = self._conds[execution_id]
        cursor = after_seq

        def _pending() -> list[DebugEvent]:
            merged = [
                e
                for e in (*self._events[execution_id], *self._audio[execution_id])
                if e.seq > cursor
            ]
            merged.sort(key=lambda e: e.seq)
            return merged

        while True:
            for event in _pending():
                cursor = event.seq
                yield event
                if event.event_type in TERMINAL_EVENTS:
                    return
            async with cond:
                # Re-check under the lock so a notify between the scan and the wait isn't missed.
                if _pending():
                    continue
                await cond.wait()

    def drop(self, execution_id: UUID) -> None:
        self._events.pop(execution_id, None)
        self._audio.pop(execution_id, None)
        self._seq.pop(execution_id, None)
        self._conds.pop(execution_id, None)


class RedisStreamBuffer:
    """Cross-process buffer backed by a Redis Stream (one per execution).

    Entry payloads carry the full serialized DebugEvent (seq embedded). Replay reads the
    retained range and filters by cursor; live tailing uses XREAD BLOCK.
    """

    def __init__(self, redis: Any, max_events: int = 2000, audio_max_chunks: int = 50):
        self._redis = redis
        self._max_events = max_events
        self._audio_max_chunks = audio_max_chunks
        self._opened: set[UUID] = set()

    def _key(self, execution_id: UUID) -> str:
        return f"stream:events:{execution_id}"

    def _audio_key(self, execution_id: UUID) -> str:
        return f"stream:audio:{execution_id}"

    def open(self, execution_id: UUID) -> None:
        self._opened.add(execution_id)

    def is_open(self, execution_id: UUID) -> bool:
        return execution_id in self._opened

    async def append(self, execution_id: UUID, event: DebugEvent) -> int:
        seq = int(await self._redis.incr(f"stream:seq:{execution_id}"))
        event.seq = seq
        await self._redis.xadd(
            self._key(execution_id),
            {"payload": event.model_dump_json()},
            maxlen=self._max_events,
            approximate=True,
        )
        return seq

    async def append_transient(self, execution_id: UUID, event: DebugEvent) -> int:
        """Append a live-only audio event to a separate, small-MAXLEN stream so heavy PCM
        never evicts retained control/text. Shares the seq counter with append()."""
        seq = int(await self._redis.incr(f"stream:seq:{execution_id}"))
        event.seq = seq
        await self._redis.xadd(
            self._audio_key(execution_id),
            {"payload": event.model_dump_json()},
            maxlen=self._audio_max_chunks,
            approximate=True,
        )
        return seq

    async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        events_key = self._key(execution_id)
        audio_key = self._audio_key(execution_id)
        last = {events_key: "0-0", audio_key: "0-0"}

        # Replay retained ranges from both streams, filtered by cursor, merged by seq.
        replay: list[DebugEvent] = []
        for key in (events_key, audio_key):
            for entry_id, fields in await self._redis.xrange(key):
                last[key] = entry_id
                ev = DebugEvent.model_validate_json(fields["payload"])
                if ev.seq > after_seq:
                    replay.append(ev)
        for ev in sorted(replay, key=lambda e: e.seq):
            yield ev
            if ev.event_type in TERMINAL_EVENTS:
                return

        # Live tail both streams.
        while True:
            resp = await self._redis.xread(last, block=25_000, count=100)
            if not resp:
                continue  # keepalive tick; the endpoint pings idle clients
            batch: list[DebugEvent] = []
            for stream_key, entries in resp:
                for entry_id, fields in entries:
                    last[stream_key] = entry_id
                    ev = DebugEvent.model_validate_json(fields["payload"])
                    if ev.seq > after_seq:
                        batch.append(ev)
            for ev in sorted(batch, key=lambda e: e.seq):
                yield ev
                if ev.event_type in TERMINAL_EVENTS:
                    return

    def drop(self, execution_id: UUID) -> None:
        # Discard the local marker; the Redis key self-expires via TTL (set in Task 11).
        self._opened.discard(execution_id)
