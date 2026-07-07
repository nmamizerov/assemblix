"""Unit tests for the STREAM_DELTA debug event schema + DebugEventManager streaming."""

from datetime import datetime
from uuid import uuid4

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
