"""Regression: a parallel fork where BOTH branches write to the DB.

START(audio) ⇉ [transcribe(saveAsUserMessage), agent(audio-capable)] → END. Both
branches touch the DB inside their node body (transcribe saves the user turn; the
agent commits at its node boundary). Before session-per-branch this raised
SQLAlchemy's "concurrent operations are not permitted" on the shared session — the
exact scenario documented in test_voice_native_workflow.py, which had to avoid the
fork. Now each branch runs on its own session and the join completes.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from tests.fixtures.workflows import agent_config, edge, node

AUDIO_MODEL = "gemini-3-flash-preview"
AUDIO_FILE = ("clip.wav", b"RIFFfake-audio", "audio/wav")


def _start_config() -> dict[str, Any]:
    return {"acceptVoice": True, "voiceModel": {"provider": "openai", "model": "whisper-1"}}


async def _register_and_publish(
    api_client: Any, *, email: str, nodes: list[dict], edges: list[dict]
) -> SimpleNamespace:
    reg = await api_client.post(
        "/api/auth/register", json={"email": email, "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "fork-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    create_resp = await api_client.post(
        "/api/workflows/",
        json={
            "projectId": project_id,
            "name": "Parallel voice fork",
            "nodes": nodes,
            "edges": edges,
        },
        headers=jwt_headers,
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    publish_resp = await api_client.post(
        f"/api/workflows/{workflow_id}/publish", headers=jwt_headers
    )
    assert publish_resp.status_code == 200
    return SimpleNamespace(
        key_headers=key_headers, jwt_headers=jwt_headers, workflow_id=workflow_id
    )


async def test_parallel_fork_both_branches_write_db(
    api_client: Any, mock_llm: Any, mocker: Any
) -> None:
    # Arrange — deterministic STT + LLM; a fork where both branches persist to the DB.
    async def _fake_transcription(**_: Any) -> SimpleNamespace:
        return SimpleNamespace(text="fork transcript proof", language="en", duration=1.0)

    mocker.patch(
        "assemblix_api.external.voice.transcription.litellm.atranscription",
        side_effect=_fake_transcription,
    )
    mock_llm.set_response("agent reply")
    nodes = [
        node("start", "start", _start_config()),
        node(
            "transcribe",
            "transcribe",
            {
                "voiceModel": {"provider": "openai", "model": "whisper-1"},
                "saveAsUserMessage": True,
            },
        ),
        node(
            "agent",
            "agent",
            agent_config(provider="gemini", model=AUDIO_MODEL, instructions="Reply."),
        ),
        node("end", "end", {}),
    ]
    edges = [
        edge("start", "transcribe"),
        edge("start", "agent"),
        edge("transcribe", "end"),
        edge("agent", "end"),
    ]
    setup = await _register_and_publish(
        api_client, email="parallel-fork@example.com", nodes=nodes, edges=edges
    )

    # Act
    run = await api_client.post(
        f"/api/workflows/{setup.workflow_id}/execute/audio",
        files={"file": AUDIO_FILE},
        data={"payload": json.dumps({"input": {}, "createSession": True})},
        headers=setup.key_headers,
    )

    # Assert — no concurrency crash; the run completes and the transcribe write landed.
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "completed"
    session_id = body["sessionId"]
    detail = await api_client.get(
        f"/api/chat-sessions/{session_id}", headers=setup.jwt_headers
    )
    assert detail.status_code == 200
    user_messages = [m for m in detail.json()["messages"] if m["role"] == "user"]
    assert any(m["content"] == "fork transcript proof" for m in user_messages), (
        f"transcribe branch write missing: {user_messages}"
    )
