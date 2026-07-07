"""Unit tests for the sequence-numbered replayable stream buffer."""

import asyncio
from datetime import datetime
from uuid import uuid4

from assemblix_api.execution.stream_buffer import InMemoryStreamBuffer, RedisStreamBuffer
from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType


def _ev(eid, kind=DebugEventType.STREAM_DELTA, delta="x"):
    return DebugEvent(
        event_type=kind,
        execution_id=eid,
        timestamp=datetime.now(),
        data={"delta": delta},
        seq=0,
    )


async def test_append_assigns_monotonic_seq() -> None:
    """append() assigns 1-based, monotonically increasing seq numbers (C8)."""
    # Arrange
    buf = InMemoryStreamBuffer(max_events=100)
    eid = uuid4()
    buf.open(eid)

    # Act
    s1 = await buf.append(eid, _ev(eid))
    s2 = await buf.append(eid, _ev(eid))

    # Assert
    assert (s1, s2) == (1, 2)


async def test_subscribe_replays_after_cursor_then_completes() -> None:
    """subscribe(after_seq=N) yields only events with seq > N, ending at a terminal event (C9, C10)."""
    # Arrange
    buf = InMemoryStreamBuffer(max_events=100)
    eid = uuid4()
    buf.open(eid)
    await buf.append(eid, _ev(eid, delta="a"))  # seq 1
    await buf.append(eid, _ev(eid, delta="b"))  # seq 2
    await buf.append(eid, _ev(eid, DebugEventType.EXECUTION_COMPLETE))  # seq 3

    # Act
    got = [e async for e in buf.subscribe(eid, after_seq=1)]

    # Assert
    assert [e.seq for e in got] == [2, 3]


async def test_two_subscribers_each_get_full_stream_from_their_cursor() -> None:
    """Two live subscribers each receive the full stream from their own cursor (C12)."""
    # Arrange
    buf = InMemoryStreamBuffer(max_events=100)
    eid = uuid4()
    buf.open(eid)

    async def collect(cursor):
        return [e.seq async for e in buf.subscribe(eid, after_seq=cursor)]

    # Act
    task_a = asyncio.create_task(collect(0))
    task_b = asyncio.create_task(collect(0))
    await asyncio.sleep(0)  # let both subscribe before events arrive
    await buf.append(eid, _ev(eid))  # seq 1
    await buf.append(eid, _ev(eid, DebugEventType.EXECUTION_COMPLETE))  # seq 2

    # Assert
    assert await task_a == [1, 2]
    assert await task_b == [1, 2]


async def test_redis_buffer_replays_after_cursor_like_in_memory(fake_redis) -> None:
    """RedisStreamBuffer replays events after a cursor identically to the in-memory buffer (C11)."""
    # Arrange
    buf = RedisStreamBuffer(fake_redis, max_events=100)
    eid = uuid4()
    buf.open(eid)
    await buf.append(eid, _ev(eid, delta="a"))  # seq 1
    await buf.append(eid, _ev(eid, delta="b"))  # seq 2
    await buf.append(eid, _ev(eid, DebugEventType.EXECUTION_COMPLETE))  # seq 3

    # Act
    got = [e async for e in buf.subscribe(eid, after_seq=1)]

    # Assert
    assert [e.seq for e in got] == [2, 3]
    assert got[0].data["delta"] == "b"
