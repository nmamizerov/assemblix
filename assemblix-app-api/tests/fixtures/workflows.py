"""Builders for workflow node-graph JSON used by execution tests.

The execution engine consumes ``nodes: list[dict]`` and ``edges`` shaped like
``assemblix_api.schemas.workflow.Edge`` (id/source/target/source_handle). These
helpers assemble valid graphs so test authors don't hand-write boilerplate.

Note: these only produce the graph payload. Persisting a Workflow row and running
it goes through the normal service/executor path in the test that uses them.
"""

from __future__ import annotations

from typing import Any


def node(
    node_id: str,
    node_type: str,
    config: dict[str, Any] | None = None,
    *,
    position: dict[str, int] | None = None,
) -> dict[str, Any]:
    """A single workflow node dict (``type`` is the registry string type).

    ``position`` is included so the graph also passes the API ``Node`` schema
    (BaseNodeSchema requires it); the executor itself ignores it.
    """
    return {
        "id": node_id,
        "type": node_type,
        "position": position or {"x": 0, "y": 0},
        "config": config or {},
    }


def edge(
    source: str,
    target: str,
    *,
    source_handle: str | None = None,
    edge_id: str | None = None,
) -> dict[str, Any]:
    """A single edge. ``source_handle`` selects a CONDITION branch when set."""
    return {
        "id": edge_id or f"{source}->{target}",
        "source": source,
        "target": target,
        "source_handle": source_handle,
        "target_handle": None,
    }


def agent_config(
    *,
    provider: str = "openai",
    model: str = "gpt-4o",
    instructions: str = "You are a helpful assistant.",
    credential_id: str | None = None,
    response_format: str = "text",
    response_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimal valid AGENT node config (system instruction only).

    ``response_format="json_object"`` makes the agent parse its reply as JSON,
    exposing it to the next node as ``input.parsed_message``. ``response_schema``
    is the optional JSON schema sent to the provider for structured output.
    """
    cfg: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "instructions": [{"role": "system", "content": instructions}],
        "credential_id": credential_id,
        "response_format": response_format,
    }
    if response_schema is not None:
        cfg["response_schema"] = response_schema
    return cfg


def linear_agent_workflow(
    *,
    instructions: str = "You are a helpful assistant.",
    credential_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """START → AGENT → END graph. Returns ``(nodes, edges)``.

    Pair with the ``mock_llm`` fixture so the AGENT step returns a deterministic
    response instead of hitting a real provider.
    """
    nodes = [
        node("start", "start", {}),
        node(
            "agent", "agent", agent_config(instructions=instructions, credential_id=credential_id)
        ),
        node("end", "end", {}),
    ]
    edges = [edge("start", "agent"), edge("agent", "end")]
    return nodes, edges


def condition_branch_workflow(
    conditions: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """START → CONDITION with one END per branch (+ else branch).

    ``conditions`` are CEL expressions; branch ``i`` is reached via the
    ``source_<node_id>_<i>`` handle (matching GraphNavigator), and the final
    "else" branch uses index ``len(conditions)``.
    """
    cond_cfg = {"conditions": [{"expression": expr} for expr in conditions]}
    nodes: list[dict[str, Any]] = [
        node("start", "start", {}),
        node("cond", "condition", cond_cfg),
    ]
    edges: list[dict[str, Any]] = [edge("start", "cond")]
    for i in range(len(conditions) + 1):  # +1 for the else branch
        end_id = f"end_{i}"
        nodes.append(node(end_id, "end", {}))
        edges.append(edge("cond", end_id, source_handle=f"source_cond_{i}"))
    return nodes, edges


def routing_session_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A stateful, turn-routing workflow. Returns ``(nodes, edges)``.

    Flow:
        START
          → AGENT 1 (JSON reply → input.parsed_message)
          → SET_VARIABLE: category = input.parsed_message.category;
                          turn     = has(state.turn) ? state.turn + 1 : 1
          → CONDITION: turn == 1 → AGENT 2 ; turn == 2 → AGENT 3
          → AGENT 2 → END (keep session open)
          → AGENT 3 → END (close session)

    Run it twice on the same chat session: turn goes 1 → 2, so the first run takes
    the AGENT-2 branch and leaves the session open, the second takes AGENT-3 and
    closes it. ``category`` is updated from the agent's JSON reply each run.
    """
    nodes: list[dict[str, Any]] = [
        node("start", "start", {}),
        node(
            "agent1",
            "agent",
            agent_config(
                instructions="Classify the message and reply as JSON.",
                response_format="json_object",
                response_schema={
                    "type": "object",
                    "properties": {"category": {"type": "string"}},
                    "required": ["category"],
                },
            ),
        ),
        node(
            "setvar",
            "set_variable",
            {
                "updates": [
                    {"variable_name": "category", "value": "input.parsed_message.category"},
                    {
                        "variable_name": "turn",
                        "value": "has(state.turn) ? state.turn + 1 : 1",
                    },
                ]
            },
        ),
        node(
            "cond",
            "condition",
            {
                "conditions": [
                    {"expression": "state.turn == 1", "name": "first turn"},
                    {"expression": "state.turn == 2", "name": "second turn"},
                ]
            },
        ),
        node("agent2", "agent", agent_config(instructions="Reply for the first turn.")),
        node("agent3", "agent", agent_config(instructions="Reply for the second turn.")),
        node("end_continue", "end", {"is_session_end": False}),
        node("end_finish", "end", {"is_session_end": True}),
    ]
    edges: list[dict[str, Any]] = [
        edge("start", "agent1"),
        edge("agent1", "setvar"),
        edge("setvar", "cond"),
        edge("cond", "agent2", source_handle="source_cond_0"),
        edge("cond", "agent3", source_handle="source_cond_1"),
        edge("agent2", "end_continue"),
        edge("agent3", "end_finish"),
    ]
    return nodes, edges


def routing_session_state() -> list[dict[str, Any]]:
    """State-variable schema for ``routing_session_workflow`` (pass as ``state``).

    ``turn`` defaults to 0 so the SET_VARIABLE node increments it to 1 on the first
    run; ``category`` is filled from the agent's JSON reply.
    """
    return [
        {"name": "category", "type": "string", "defaultValue": ""},
        {"name": "turn", "type": "number", "defaultValue": 0},
    ]
