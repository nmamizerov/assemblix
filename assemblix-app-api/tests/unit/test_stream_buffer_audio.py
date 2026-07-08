from datetime import datetime
from uuid import uuid4

import pytest

from assemblix_api.execution.stream_buffer import InMemoryStreamBuffer
from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType


def _evt(exec_id, etype):
    return DebugEvent(event_type=etype, execution_id=exec_id, timestamp=datetime.now(), data={})


@pytest.mark.asyncio
async def test_transient_audio_delivered_live_and_ordered():
    # Arrange
    buf = InMemoryStreamBuffer(max_events=2000, audio_max_chunks=50)
    exec_id = uuid4()
    buf.open(exec_id)
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STEP_START))
    await buf.append_transient(exec_id, _evt(exec_id, DebugEventType.AUDIO_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STREAM_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.EXECUTION_COMPLETE))
    # Act
    got = [e.event_type async for e in buf.subscribe(exec_id, after_seq=0)]
    # Assert
    assert got == [
        DebugEventType.STEP_START,
        DebugEventType.AUDIO_DELTA,
        DebugEventType.STREAM_DELTA,
        DebugEventType.EXECUTION_COMPLETE,
    ]


@pytest.mark.asyncio
async def test_audio_ring_overflow_does_not_evict_retained():
    # Arrange
    buf = InMemoryStreamBuffer(max_events=2000, audio_max_chunks=2)
    exec_id = uuid4()
    buf.open(exec_id)
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STEP_START))
    for _ in range(5):  # overflow the audio ring of 2
        await buf.append_transient(exec_id, _evt(exec_id, DebugEventType.AUDIO_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.EXECUTION_COMPLETE))
    # Act
    got = [e.event_type async for e in buf.subscribe(exec_id, after_seq=0)]
    # Assert — the retained control events survive; at most 2 audio remain
    assert got[0] == DebugEventType.STEP_START
    assert got[-1] == DebugEventType.EXECUTION_COMPLETE
    assert got.count(DebugEventType.AUDIO_DELTA) <= 2
