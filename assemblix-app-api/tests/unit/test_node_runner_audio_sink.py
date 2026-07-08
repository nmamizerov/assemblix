import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.execution.node_runner import NodeRunner
from assemblix_api.schemas.debug_events import AlignmentData
from assemblix_api.schemas.execution import NodeInput, NodeOutput


@pytest.mark.asyncio
async def test_audio_sink_forwards_to_emit_audio_delta():
    # Arrange
    exec_id = uuid4()
    dem = DebugEventManager()
    dem.open_buffer(exec_id)
    dem.emit_audio_delta = AsyncMock()
    runner = NodeRunner(Mock(), dem, AsyncMock())
    ctx = SimpleNamespace(stream_enabled=True, execution_id=exec_id)
    node_input = NodeInput(data={}, context=ctx)
    captured: dict = {}

    async def _execute(ni):
        captured["on_audio"] = ni.on_audio
        return NodeOutput(data={})

    node = SimpleNamespace(execute=_execute)
    # Act
    await runner.run(node, node_input, node_id="agent-1", step_number=4)
    await captured["on_audio"](
        b"\x09\x08", AlignmentData(chars=["x"], char_start_times_ms=[0], char_durations_ms=[10])
    )
    # Assert
    dem.emit_audio_delta.assert_awaited_once()
    kwargs = dem.emit_audio_delta.await_args.kwargs
    assert kwargs["node_id"] == "agent-1"
    assert kwargs["step_number"] == 4
    assert kwargs["audio"] == base64.b64encode(b"\x09\x08").decode("ascii")
