"""Unit tests for the STREAM_DELTA `avatar` flag (avatar-node stream tagging)."""

from decimal import Decimal
from uuid import uuid4

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.debug_events import DebugEventType, StreamDeltaEventData


def test_stream_delta_data_has_avatar_default_false() -> None:
    """StreamDeltaEventData.avatar defaults to False for non-avatar deltas."""
    # Arrange / Act
    data = StreamDeltaEventData(node_id="n1", step_number=1, delta="hi")

    # Assert
    assert data.avatar is False


async def test_emit_stream_delta_sets_avatar_flag() -> None:
    """emit_stream_delta(avatar=True) tags the buffered STREAM_DELTA event's data."""
    # Arrange
    mgr = DebugEventManager()
    execution_id = uuid4()
    mgr.create_stream(execution_id)

    # Act
    await mgr.emit_stream_delta(execution_id, step_number=1, node_id="n1", delta="hi", avatar=True)
    await mgr.emit_execution_complete(
        execution_id,
        status="completed",
        output={},
        final_state={},
        final_project_state={},
        total_steps=1,
        total_credits=Decimal("0"),
        duration_ms=1,
    )
    events = [e async for e in mgr.subscribe(execution_id, after_seq=0)]

    # Assert
    delta_events = [e for e in events if e.event_type == DebugEventType.STREAM_DELTA]
    assert delta_events and delta_events[0].data["avatar"] is True
