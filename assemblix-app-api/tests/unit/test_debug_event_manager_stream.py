"""Unit tests for the STREAM_DELTA debug event schema + DebugEventManager streaming."""

import asyncio
import types
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import assemblix_api.execution.debug_event_manager as dem
from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.debug_events import (
    DebugEvent,
    DebugEventType,
    StreamDeltaEventData,
)


def test_stream_delta_event_serializes_with_seq() -> None:
    """A STREAM_DELTA DebugEvent serializes with a top-level seq and snake_case keys."""
    # Arrange
    data = StreamDeltaEventData(node_id="agent-1", step_number=2, delta="Hi")
    event = DebugEvent(
        event_type=DebugEventType.STREAM_DELTA,
        execution_id=uuid4(),
        timestamp=datetime.now(),
        data=data.model_dump(),
        seq=7,
    )

    # Assert — the existing debug SSE serializes via model_dump(mode="json") -> snake_case
    dumped = event.model_dump(mode="json")
    assert dumped["event_type"] == "stream_delta"
    assert dumped["seq"] == 7
    assert dumped["data"]["delta"] == "Hi"
    assert dumped["data"]["node_id"] == "agent-1"
    assert dumped["data"]["step_number"] == 2


async def test_emit_stream_delta_is_buffered_and_subscribable() -> None:
    """emit_stream_delta lands in the buffer with a seq and is replayable via subscribe()."""
    # Arrange
    mgr = DebugEventManager()
    eid = uuid4()
    mgr.create_stream(eid)
    assert mgr.is_streaming(eid) is True

    # Act
    await mgr.emit_stream_delta(eid, step_number=1, node_id="agent-1", delta="Hi")
    await mgr.emit_execution_complete(
        eid,
        status="completed",
        output={},
        final_state={},
        final_project_state={},
        total_steps=1,
        total_credits=Decimal("0"),
        duration_ms=1,
    )
    events = [e async for e in mgr.subscribe(eid, after_seq=0)]

    # Assert
    kinds = [e.event_type for e in events]
    assert DebugEventType.STREAM_DELTA in kinds
    assert events[0].seq == 1
    assert events[0].data["delta"] == "Hi"
    assert events[0].data["node_id"] == "agent-1"


async def test_open_buffer_streams_without_legacy_queue() -> None:
    """A streaming-only run opens the replayable buffer but NOT the legacy asyncio.Queue."""
    # Arrange / Act
    mgr = DebugEventManager()
    eid = uuid4()
    mgr.open_buffer(eid)

    # Assert
    assert mgr.is_streaming(eid) is True
    assert mgr.get_stream(eid) is None  # no undrained legacy queue for a streaming-only run


async def test_buffer_dropped_after_ttl(monkeypatch) -> None:
    """schedule_stream_cleanup drops the buffer after the configured TTL."""
    # Arrange
    monkeypatch.setattr(
        dem, "get_settings", lambda: types.SimpleNamespace(stream_buffer_ttl_seconds=0)
    )
    mgr = DebugEventManager()
    eid = uuid4()
    mgr.create_stream(eid)

    # Act
    mgr.schedule_stream_cleanup(eid)
    await asyncio.sleep(0.05)  # let the scheduled task run (ttl=0)

    # Assert
    assert mgr.is_streaming(eid) is False
