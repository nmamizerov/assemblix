"""End-to-end streaming integration: mid-stream error, parallel demux, non-stream regression."""

import asyncio
import json
from types import SimpleNamespace

from tests.fixtures.workflows import agent_config, edge, linear_agent_workflow, node


async def _register(api_client) -> SimpleNamespace:
    reg = await api_client.post(
        "/api/auth/register", json={"email": "e2e@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]
    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "e2e-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}
    return SimpleNamespace(jwt_headers=jwt_headers, key_headers=key_headers, project_id=project_id)


async def _create_publish(api_client, auth, nodes, edges) -> str:
    create_resp = await api_client.post(
        "/api/workflows/",
        json={"projectId": auth.project_id, "name": "E2E", "nodes": nodes, "edges": edges},
        headers=auth.jwt_headers,
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]
    publish_resp = await api_client.post(
        f"/api/workflows/{workflow_id}/publish", headers=auth.jwt_headers
    )
    assert publish_resp.status_code == 200
    return workflow_id


def _sse_frames(text: str) -> list[dict]:
    """Parse an SSE body into [{event, data(dict|None)}]."""
    frames = []
    for block in text.split("\n\n"):
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[len("data: ") :])
                except json.JSONDecodeError:
                    data = None
        if event:
            frames.append({"event": event, "data": data})
    return frames


def _streamable_linear() -> tuple[list, list]:
    nodes, edges = linear_agent_workflow()
    for n in nodes:
        if n["type"] == "agent":
            n["config"]["stream"] = True
    return nodes, edges


async def test_non_stream_debug_has_no_deltas(api_client, mock_llm) -> None:
    """A debug run with the streaming toggle OFF emits no stream_delta events (E16)."""
    # Arrange
    mock_llm.set_response("plain answer")
    auth = await _register(api_client)
    nodes, edges = _streamable_linear()  # agent has stream=True in config, but request won't ask
    workflow_id = await _create_publish(api_client, auth, nodes, edges)

    # Act — /execute/debug does NOT send stream=true
    resp = await asyncio.wait_for(
        api_client.post(
            f"/api/workflows/{workflow_id}/execute/debug",
            json={"input": {"message": "hi"}},
            headers=auth.key_headers,
        ),
        timeout=30.0,
    )

    # Assert
    assert resp.status_code == 200
    assert "event: stream_delta" not in resp.text
    assert "event: step_start" in resp.text
    assert "event: execution_complete" in resp.text


async def test_error_mid_stream_marks_failed_and_keeps_partials(api_client, mock_llm) -> None:
    """An LLM error mid-stream keeps the delivered deltas, ends with error, marks FAILED (D14)."""
    # Arrange
    mock_llm.set_stream_error(["par", "tial"], "provider exploded")
    auth = await _register(api_client)
    nodes, edges = _streamable_linear()
    workflow_id = await _create_publish(api_client, auth, nodes, edges)

    # Act
    run = await api_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input": {"message": "hi"}, "task": True, "stream": True},
        headers=auth.key_headers,
    )
    execution_id = run.json()["executionId"]
    stream = await asyncio.wait_for(
        api_client.get(
            f"/api/executions/{execution_id}/stream", headers=auth.jwt_headers
        ),
        timeout=30.0,
    )
    frames = _sse_frames(stream.text)

    # Assert
    assert any(f["event"] == "stream_delta" for f in frames)  # partials delivered
    assert frames[-1]["event"] == "error"
    detail = await api_client.get(
        f"/api/executions/{execution_id}", headers=auth.jwt_headers
    )
    assert detail.json()["status"] == "FAILED"


async def test_parallel_streamable_agents_demux_by_node_id(api_client, mock_llm) -> None:
    """Two parallel streamable agents produce deltas distinguishable by node_id (D15)."""
    # Arrange
    mock_llm.set_stream(["Hello", " world"])
    auth = await _register(api_client)
    cfg_a = agent_config()
    cfg_a["stream"] = True
    cfg_b = agent_config()
    cfg_b["stream"] = True
    nodes = [
        node("start-1", "start", {}),
        node("agent-a", "agent", cfg_a),
        node("agent-b", "agent", cfg_b),
        node("end-1", "end", {}),
    ]
    edges = [
        edge("start-1", "agent-a"),
        edge("start-1", "agent-b"),
        edge("agent-a", "end-1"),
        edge("agent-b", "end-1"),
    ]
    workflow_id = await _create_publish(api_client, auth, nodes, edges)

    # Act
    run = await api_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input": {"message": "hi"}, "task": True, "stream": True},
        headers=auth.key_headers,
    )
    execution_id = run.json()["executionId"]
    stream = await asyncio.wait_for(
        api_client.get(
            f"/api/executions/{execution_id}/stream", headers=auth.jwt_headers
        ),
        timeout=30.0,
    )
    frames = _sse_frames(stream.text)

    # Assert
    node_ids = {
        f["data"]["data"]["node_id"]
        for f in frames
        if f["event"] == "stream_delta" and f["data"]
    }
    assert node_ids == {"agent-a", "agent-b"}
