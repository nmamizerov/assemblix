"""End-to-end API tests for a stateful turn-routing workflow.

Exercises the real production path over HTTP — register → create API key →
create workflow (with state schema) → publish → execute — verifying:

* state update — `category` (from the agent's JSON reply) and `turn` (incrementing
  from persisted session state);
* conditional routing by `turn` — run 1 → AGENT 2, run 2 → AGENT 3;
* session lifecycle — run 1 keeps the session open, run 2 closes it;
* debug execution — `/execute/debug` streams SSE events to completion.

The LLM is mocked at the single `litellm.acompletion` seam, so we test our API and
orchestration (routing, state, session), not the provider.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest_asyncio

from tests.fixtures.workflows import routing_session_state, routing_session_workflow


async def _register_key_and_workflow(api_client) -> SimpleNamespace:
    """Shared setup: register a user, mint an API key, create the routing workflow.

    Returns a namespace with ``jwt_headers``, ``key_headers``, ``project_id`` and
    ``workflow_id`` (the draft — publish it in the test if needed).
    """
    reg = await api_client.post(
        "/api/auth/register", json={"email": "router@example.com", "password": "pass1234"}
    )
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

    nodes, edges = routing_session_workflow()
    create_resp = await api_client.post(
        "/api/workflows/",
        json={
            "projectId": project_id,
            "name": "Routing workflow",
            "nodes": nodes,
            "edges": edges,
            "state": routing_session_state(),
        },
        headers=jwt_headers,
    )
    assert create_resp.status_code == 201

    return SimpleNamespace(
        jwt_headers=jwt_headers,
        key_headers=key_headers,
        project_id=project_id,
        workflow_id=create_resp.json()["id"],
    )


@pytest_asyncio.fixture
async def routing_setup(api_client, mock_llm) -> SimpleNamespace:
    """Per-test setup (pytest's ``@BeforeEach`` equivalent).

    Arms the mocked agent to always classify the message as ``{"category": "support"}``
    and provisions the user/key/workflow via :func:`_register_key_and_workflow`.
    """
    mock_llm.set_response('{"category": "support"}')
    return await _register_key_and_workflow(api_client)


async def test_routing_workflow_via_api_runs_twice(api_client, routing_setup) -> None:
    """Publish, then run the workflow twice on one chat session."""
    # Arrange — publish the draft (execute runs the latest published version).
    publish_resp = await api_client.post(
        f"/api/workflows/{routing_setup.workflow_id}/publish", headers=routing_setup.jwt_headers
    )
    assert publish_resp.status_code == 200

    # Act — first run (create a new chat session).
    run1 = await api_client.post(
        f"/api/workflows/{routing_setup.workflow_id}/execute",
        json={"input": {"message": "I need help"}, "createSession": True},
        headers=routing_setup.key_headers,
    )

    # Assert — first run: state updated, turn == 1, session stays open (AGENT 2 branch).
    assert run1.status_code == 200
    body1 = run1.json()
    assert body1["status"] == "completed"
    assert body1["state"]["category"] == "support"
    assert body1["state"]["turn"] == 1
    assert body1["isSessionClosed"] is False
    session_id = body1["sessionId"]
    assert session_id

    # Act — second run on the SAME session (turn carries over and increments).
    run2 = await api_client.post(
        f"/api/workflows/{routing_setup.workflow_id}/execute",
        json={"input": {"message": "still need help"}, "sessionId": session_id},
        headers=routing_setup.key_headers,
    )

    # Assert — second run: turn == 2, session is closed (AGENT 3 branch).
    assert run2.status_code == 200
    body2 = run2.json()
    assert body2["status"] == "completed"
    assert body2["state"]["category"] == "support"
    assert body2["state"]["turn"] == 2
    assert body2["isSessionClosed"] is True


async def test_debug_run_streams_events(api_client, routing_setup, mock_llm) -> None:
    """POST /execute/debug streams SSE events for a draft run until completion."""
    # Act — run in debug mode (runs the draft directly, no publish) and drain the SSE.
    resp = await asyncio.wait_for(
        api_client.post(
            f"/api/workflows/{routing_setup.workflow_id}/execute/debug",
            json={"input": {"message": "I need help"}},
            headers=routing_setup.key_headers,
        ),
        timeout=30.0,
    )

    # Assert — SSE stream started, ran the agent, and finished without an error event.
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "event: execution_started" in resp.text
    assert "event: execution_complete" in resp.text
    assert "event: error" not in resp.text
    assert mock_llm.call_count >= 1
