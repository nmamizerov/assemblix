from uuid import uuid4

import pytest

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.debug_events import AlignmentData, DebugEventType


@pytest.mark.asyncio
async def test_emit_audio_delta_is_live_transient():
    # Arrange
    mgr = DebugEventManager()
    exec_id = uuid4()
    mgr.open_buffer(exec_id)
    # Act
    await mgr.emit_audio_delta(
        exec_id,
        step_number=2,
        node_id="agent-1",
        audio="QUJD",
        alignment=AlignmentData(chars=["A"], char_start_times_ms=[0], char_durations_ms=[40]),
    )
    got = []
    async for e in mgr.subscribe(exec_id, after_seq=0):
        got.append(e)
        break  # first event only; no terminal is emitted in this test
    # Assert
    assert got[0].event_type == DebugEventType.AUDIO_DELTA
    assert got[0].data["audio"] == "QUJD"
