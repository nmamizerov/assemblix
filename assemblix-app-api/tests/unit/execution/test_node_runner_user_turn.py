"""Unit test for NodeRunner.record_completed folding NodeOutput.user_turn into the
shared context — the channel the transcribe node uses so a downstream agent sees the
transcript as the current user turn, without corrupting last_history_message (which
finalization uses to persist the assistant reply)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.execution.node_runner import NodeRunner
from assemblix_api.schemas.execution import NodeOutput
from tests.unit.nodes._helpers import make_context


async def test_record_completed_folds_user_turn_into_chat_history() -> None:
    # Arrange
    tracer = Mock()
    tracer.has_step = AsyncMock(return_value=True)  # skip log_step; not under test here
    dem = DebugEventManager()  # no buffer opened -> is_streaming() False
    runner = NodeRunner(tracer, dem, AsyncMock())
    context = make_context(chat_history=[{"role": "assistant", "content": "prior answer"}])
    node_output = NodeOutput(data={"message": "hello"}, user_turn="hello")

    # Act
    updated = await runner.record_completed(
        context,
        node_id="transcribe-1",
        node_type="transcribe",
        node_data={},
        node_output=node_output,
        state_before={},
        step_number=1,
        started_at=datetime.now(),
    )

    # Assert
    assert updated.chat_history == [
        {"role": "assistant", "content": "prior answer"},
        {"role": "user", "content": "hello"},
    ]
    assert updated.last_history_message is None  # untouched by the user-turn fold
