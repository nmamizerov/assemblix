"""Integration tests for the subscribe-by-id streaming SSE endpoint."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest_asyncio

from tests.fixtures.workflows import linear_agent_workflow


async def _create_streamable_workflow(api_client) -> SimpleNamespace:
    """Register a user, mint an API key, create + publish a START->AGENT(stream)->END workflow."""
    reg = await api_client.post(
        "/api/auth/register", json={"email": "streamer@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "stream-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    nodes, edges = linear_agent_workflow()
    for n in nodes:
        if n["type"] == "agent":
            n["config"]["stream"] = True

    create_resp = await api_client.post(
        "/api/workflows/",
        json={"projectId": project_id, "name": "Streamable", "nodes": nodes, "edges": edges},
        headers=jwt_headers,
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    publish_resp = await api_client.post(
        f"/api/workflows/{workflow_id}/publish", headers=jwt_headers
    )
    assert publish_resp.status_code == 200

    return SimpleNamespace(
        jwt_headers=jwt_headers, key_headers=key_headers, workflow_id=workflow_id
    )


@pytest_asyncio.fixture
async def streamable_setup(api_client, mock_llm) -> SimpleNamespace:
    mock_llm.set_stream(["Hello", " world"])
    return await _create_streamable_workflow(api_client)


async def test_stream_delivers_deltas_then_completes(api_client, streamable_setup) -> None:
    """A stream=true run delivers stream_delta frames and ends with execution_complete."""
    # Arrange / Act — task=true returns the execution id immediately
    run = await api_client.post(
        f"/api/workflows/{streamable_setup.workflow_id}/execute",
        json={"input": {"message": "hi"}, "task": True, "stream": True},
        headers=streamable_setup.key_headers,
    )
    assert run.status_code in (200, 202)
    execution_id = run.json()["executionId"]

    stream = await asyncio.wait_for(
        api_client.get(
            f"/api/executions/{execution_id}/stream",
            headers=streamable_setup.jwt_headers,
        ),
        timeout=30.0,
    )

    # Assert
    assert stream.status_code == 200
    assert "text/event-stream" in stream.headers["content-type"]
    assert "event: stream_delta" in stream.text
    assert "event: execution_complete" in stream.text


async def test_stream_404_when_no_active_stream(api_client, streamable_setup) -> None:
    """A missing execution has no buffer -> 404 (client falls back to task polling)."""
    # Act
    resp = await api_client.get(
        f"/api/executions/{uuid4()}/stream",
        headers=streamable_setup.jwt_headers,
    )

    # Assert
    assert resp.status_code == 404
