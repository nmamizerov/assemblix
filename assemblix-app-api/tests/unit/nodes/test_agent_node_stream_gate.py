"""Three-gate delta emission for the AGENT node: request.stream x node.stream x text format."""

import types
from decimal import Decimal

import pytest

from assemblix_api.enums import PlanTier
from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.execution.node_runner import NodeRunner
from assemblix_api.nodes.agent_node import AgentNode
from assemblix_api.schemas.debug_events import DebugEventType

from ._helpers import build_node, make_context, node_input


class _FakeResolver:
    async def resolve(self, **_kwargs) -> tuple[str, bool]:
        return "sk-test", True


async def _noop() -> None:
    return None


def _agent(*, stream: bool, response_format: str) -> AgentNode:
    return build_node(
        AgentNode,
        "agent",
        {
            "name": "Agent",
            "provider": "openai",
            "model": "gpt-4o",
            "instructions": [{"role": "system", "content": "You are helpful."}],
            "stream": stream,
            "response_format": response_format,
        },
    )


async def _count_deltas(mgr: DebugEventManager, eid) -> int:
    # Emit a terminal event so subscribe() replays the buffer and returns.
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
    count = 0
    async for e in mgr.subscribe(eid, 0):
        if e.event_type == DebugEventType.STREAM_DELTA:
            count += 1
    return count


@pytest.mark.parametrize(
    "req_stream,node_stream,response_format,expect_deltas",
    [
        (True, True, "text", True),  # A4 — all gates open
        (False, True, "text", False),  # A1 — request gate closed
        (True, False, "text", False),  # A2 — node gate closed
        (True, True, "json_object", False),  # A3 — format gate closed
    ],
)
async def test_three_gate_delta_emission(
    mock_llm, req_stream, node_stream, response_format, expect_deltas
) -> None:
    """Deltas are emitted iff request.stream AND node.stream AND response_format=='text'."""
    # Arrange
    if response_format == "json_object":
        mock_llm.set_response('{"k": "v"}')
    else:
        mock_llm.set_stream(["Hel", "lo"])
    context = make_context(
        stream_enabled=req_stream,
        credential_service=types.SimpleNamespace(),
        credential_resolver=_FakeResolver(),
        organization_plan=PlanTier.PRO,
        chat_history=[{"role": "user", "content": "hi"}],
    )
    eid = context.execution_id
    mgr = DebugEventManager()
    mgr.create_stream(eid)
    node = _agent(stream=node_stream, response_format=response_format)
    runner = NodeRunner(
        tracer=types.SimpleNamespace(), debug_event_manager=mgr, db_checkpoint=_noop
    )

    # Act
    await runner.run(
        node, node_input({"message": "hi"}, context), node_id="agent-1", step_number=1
    )

    # Assert
    assert (await _count_deltas(mgr, eid) > 0) is expect_deltas
