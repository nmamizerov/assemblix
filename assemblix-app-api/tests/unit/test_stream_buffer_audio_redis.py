from datetime import datetime
from uuid import uuid4

import pytest

from assemblix_api.execution.stream_buffer import RedisStreamBuffer
from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType


def _evt(exec_id, etype):
    return DebugEvent(event_type=etype, execution_id=exec_id, timestamp=datetime.now(), data={})


@pytest.mark.asyncio
async def test_redis_transient_audio_interleaves_by_seq(fake_redis):
    # Arrange
    buf = RedisStreamBuffer(fake_redis, max_events=2000, audio_max_chunks=50)
    exec_id = uuid4()
    buf.open(exec_id)
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STEP_START))
    await buf.append_transient(exec_id, _evt(exec_id, DebugEventType.AUDIO_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.EXECUTION_COMPLETE))
    # Act
    got = [e.event_type async for e in buf.subscribe(exec_id, after_seq=0)]
    # Assert
    assert got == [
        DebugEventType.STEP_START,
        DebugEventType.AUDIO_DELTA,
        DebugEventType.EXECUTION_COMPLETE,
    ]
