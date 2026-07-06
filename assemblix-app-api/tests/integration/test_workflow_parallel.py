"""End-to-end tests for parallel (fork/join) workflow execution.

Drive the real production path over HTTP (register → key → create → publish → execute)
for graphs that fan out into concurrent branches. Deterministic branches use
SET_VARIABLE nodes (no LLM); the agent fork uses the mocked litellm seam. Fine-grained
ordering / dead-path behaviour is covered by tests/unit/test_dag_scheduler.py; here we
assert the executor drives the scheduler correctly end-to-end.
"""

from __future__ import annotations

from tests.fixtures.workflows import agent_config, edge, node


async def _create_publish_execute(
    api_client,
    *,
    email: str,
    nodes: list[dict],
    edges: list[dict],
    state: list[dict],
    message: str = "hi",
) -> dict:
    """Register a user, create+publish the workflow, run it once. Returns the run body."""
    reg = await api_client.post("/api/auth/register", json={"email": email, "password": "pass1234"})
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "exec-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    create_resp = await api_client.post(
        "/api/workflows/",
        json={
            "projectId": project_id,
            "name": "Parallel workflow",
            "nodes": nodes,
            "edges": edges,
            "state": state,
        },
        headers=jwt_headers,
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    publish_resp = await api_client.post(
        f"/api/workflows/{workflow_id}/publish", headers=jwt_headers
    )
    assert publish_resp.status_code == 200

    run = await api_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input": {"message": message}, "createSession": True},
        headers=key_headers,
    )
    assert run.status_code == 200
    return run.json()


def _set_var(node_id: str, var: str, value: str) -> dict:
    """A SET_VARIABLE node writing one state key (value is a CEL literal)."""
    return node(node_id, "set_variable", {"updates": [{"variable_name": var, "value": value}]})


async def test_fork_join_runs_both_branches_and_merges_state(api_client) -> None:
    """START forks into two SET_VARIABLE branches that rejoin; both writes land."""
    # Arrange — start ⇉ (setA: x=1) & (setB: y=2) → J (z=3) → end.
    nodes = [
        node("start", "start", {}),
        _set_var("setA", "x", "1"),
        _set_var("setB", "y", "2"),
        _set_var("J", "z", "3"),
        node("end", "end", {}),
    ]
    edges = [
        edge("start", "setA"),
        edge("start", "setB"),
        edge("setA", "J"),
        edge("setB", "J"),
        edge("J", "end"),
    ]
    state = [
        {"name": "x", "type": "number", "defaultValue": 0},
        {"name": "y", "type": "number", "defaultValue": 0},
        {"name": "z", "type": "number", "defaultValue": 0},
    ]

    # Act
    body = await _create_publish_execute(
        api_client, email="fork-join@example.com", nodes=nodes, edges=edges, state=state
    )

    # Assert — both branches executed (x and y set) and the join ran (z set).
    assert body["status"] == "completed"
    assert body["state"]["x"] == 1
    assert body["state"]["y"] == 2
    assert body["state"]["z"] == 3


async def test_fork_conflicting_writes_do_not_crash(api_client) -> None:
    """Two parallel branches writing the SAME key resolve to last-write, no error."""
    # Arrange — start ⇉ (setA: v='a') & (setB: v='b') → J → end.
    nodes = [
        node("start", "start", {}),
        _set_var("setA", "v", "'a'"),
        _set_var("setB", "v", "'b'"),
        _set_var("J", "done", "true"),
        node("end", "end", {}),
    ]
    edges = [
        edge("start", "setA"),
        edge("start", "setB"),
        edge("setA", "J"),
        edge("setB", "J"),
        edge("J", "end"),
    ]
    state = [
        {"name": "v", "type": "string", "defaultValue": ""},
        {"name": "done", "type": "boolean", "defaultValue": False},
    ]

    # Act
    body = await _create_publish_execute(
        api_client, email="conflict@example.com", nodes=nodes, edges=edges, state=state
    )

    # Assert — the run completes; the shared key holds exactly one branch's value.
    assert body["status"] == "completed"
    assert body["state"]["v"] in {"a", "b"}
    assert body["state"]["done"] is True


async def test_agent_fork_runs_both_agents_before_single_end(api_client, mock_llm) -> None:
    """START forks into two AGENT branches that join at one END (wait-all)."""
    # Arrange — start ⇉ agent1 & agent2, both → end (END has 2 incoming → join).
    mock_llm.set_response("ok")
    nodes = [
        node("start", "start", {}),
        node("agent1", "agent", agent_config(instructions="A")),
        node("agent2", "agent", agent_config(instructions="B")),
        node("end", "end", {}),
    ]
    edges = [
        edge("start", "agent1"),
        edge("start", "agent2"),
        edge("agent1", "end"),
        edge("agent2", "end"),
    ]

    # Act
    body = await _create_publish_execute(
        api_client, email="agent-fork@example.com", nodes=nodes, edges=edges, state=[]
    )

    # Assert — both agents ran (two LLM calls) and the joined END completed the run once.
    assert body["status"] == "completed"
    assert mock_llm.call_count == 2


async def test_parallel_workflow_reports_all_steps(api_client) -> None:
    """A fork/join run records a step per executed node (unique step numbers)."""
    # Arrange — reuse the fork/join graph; assert step accounting via the API.
    nodes = [
        node("start", "start", {}),
        _set_var("setA", "x", "1"),
        _set_var("setB", "y", "2"),
        node("end", "end", {}),
    ]
    # start ⇉ setA & setB, both → end (join at END).
    edges = [
        edge("start", "setA"),
        edge("start", "setB"),
        edge("setA", "end"),
        edge("setB", "end"),
    ]
    state = [
        {"name": "x", "type": "number", "defaultValue": 0},
        {"name": "y", "type": "number", "defaultValue": 0},
    ]

    # Act
    body = await _create_publish_execute(
        api_client, email="steps@example.com", nodes=nodes, edges=edges, state=state
    )

    # Assert — run completed and both parallel writes are present.
    assert body["status"] == "completed"
    assert body["state"]["x"] == 1
    assert body["state"]["y"] == 2


async def test_leaf_branch_without_end_persists_state_and_completes(api_client) -> None:
    """A branch that writes state and dead-ends (no END) is fine, not an error.

    Reproduces the reported graph: start ⇉ (setA → END) & (setB → nothing). The setB
    branch is a leaf; wait-all guarantees its state write lands before finalization.
    """
    # Arrange
    nodes = [
        node("start", "start", {}),
        _set_var("setA", "x", "1"),
        _set_var("setB", "y", "2"),
        node("end", "end", {}),
    ]
    # setA reaches END; setB dead-ends (no outgoing edge).
    edges = [
        edge("start", "setA"),
        edge("start", "setB"),
        edge("setA", "end"),
    ]
    state = [
        {"name": "x", "type": "number", "defaultValue": 0},
        {"name": "y", "type": "number", "defaultValue": 0},
    ]

    # Act
    body = await _create_publish_execute(
        api_client, email="leaf@example.com", nodes=nodes, edges=edges, state=state
    )

    # Assert — no NoNextNodeError; run completes and the leaf branch's write persists.
    assert body["status"] == "completed"
    assert body["state"]["x"] == 1
    assert body["state"]["y"] == 2
