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
from uuid import UUID

from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType

TERMINAL_EVENTS = {DebugEventType.EXECUTION_COMPLETE, DebugEventType.ERROR}


class InMemoryStreamBuffer:
    """Retains events per execution and fans out live to any number of subscribers."""

    def __init__(self, max_events: int = 2000):
        self._max_events = max_events
        self._events: dict[UUID, deque[DebugEvent]] = {}
        self._seq: dict[UUID, int] = {}
        self._conds: dict[UUID, asyncio.Condition] = {}

    def open(self, execution_id: UUID) -> None:
        self._events.setdefault(execution_id, deque(maxlen=self._max_events))
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

    async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        if execution_id not in self._events:
            return
        cond = self._conds[execution_id]
        cursor = after_seq
        while True:
            pending = [e for e in list(self._events[execution_id]) if e.seq > cursor]
            for event in pending:
                cursor = event.seq
                yield event
                if event.event_type in TERMINAL_EVENTS:
                    return
            async with cond:
                # Re-check under the lock so a notify between the scan and the wait isn't missed.
                if any(e.seq > cursor for e in self._events[execution_id]):
                    continue
                await cond.wait()

    def drop(self, execution_id: UUID) -> None:
        self._events.pop(execution_id, None)
        self._seq.pop(execution_id, None)
        self._conds.pop(execution_id, None)
