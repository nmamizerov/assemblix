"""End-to-end API test for voice execution (`POST /execute/audio`).

Exercises the real production path over HTTP — register → create API key →
create a workflow whose START accepts voice → publish → execute with an audio
blob (multipart). The transcription seam (`litellm.atranscription`) is mocked, so
we test our own wiring: the blob is transcribed and the transcript is what the
agent receives as the user message. Run twice with different transcripts to prove
the audio path works on every call.

START now hands raw audio straight to the next node (see
``tests/integration/test_voice_native_workflow.py``), so a Transcribe node sits
between START and AGENT to normalize audio -> text before the agent runs — the
agent's default model (openai/gpt-4o) doesn't accept audio content parts.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest_asyncio

from tests.fixtures.workflows import agent_config, edge, node


def _voice_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """START (accepts voice) → transcribe → AGENT → END.

    The transcribe node injects the transcript into the run's chat_history as the
    current USER turn (``NodeOutput.user_turn`` → ``ExecutionContext.with_user_turn``,
    folded in ``NodeRunner.record_completed``) — that is the real bridge a downstream
    agent relies on. It also still writes ``input.message``/``input_type="text"`` on
    ``node_input.data`` for template rendering; this workflow's agent additionally
    picks it up via a CEL template to exercise that path too, but the template is not
    the load-bearing channel — see
    ``test_voice_native_workflow.py::test_transcribe_bridges_transcript_to_agent_via_chat_history``
    for a regression test with no template at all.
    """
    agent_cfg = agent_config(instructions="Reply to the user.")
    agent_cfg["instructions"].append({"role": "user", "content": "{{input.message}}"})
    nodes = [
        node(
            "start",
            "start",
            {"acceptVoice": True, "voiceModel": {"provider": "openai", "model": "whisper-1"}},
        ),
        node(
            "transcribe",
            "transcribe",
            {"voiceModel": {"provider": "openai", "model": "whisper-1"}},
        ),
        node("agent", "agent", agent_cfg),
        node("end", "end", {}),
    ]
    edges = [edge("start", "transcribe"), edge("transcribe", "agent"), edge("agent", "end")]
    return nodes, edges


@pytest_asyncio.fixture
async def voice_setup(api_client, mock_llm) -> SimpleNamespace:
    """Register a user, mint an API key, create + publish the voice workflow."""
    mock_llm.set_response("agent reply")

    reg = await api_client.post(
        "/api/auth/register", json={"email": "voice@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "voice-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    nodes, edges = _voice_workflow()
    create_resp = await api_client.post(
        "/api/workflows/",
        json={"projectId": project_id, "name": "Voice workflow", "nodes": nodes, "edges": edges},
        headers=jwt_headers,
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    publish_resp = await api_client.post(
        f"/api/workflows/{workflow_id}/publish", headers=jwt_headers
    )
    assert publish_resp.status_code == 200

    return SimpleNamespace(key_headers=key_headers, workflow_id=workflow_id)


async def test_execute_audio_transcribes_and_feeds_agent_twice(
    api_client, voice_setup, mock_llm, mocker: Any
) -> None:
    """Two /execute/audio calls: each blob is transcribed and reaches the agent."""
    # Arrange — mock the transcription seam to return a distinct text per call.
    transcripts = iter(["first voice message", "second voice message"])

    async def _fake_transcription(**_: Any) -> SimpleNamespace:
        return SimpleNamespace(text=next(transcripts), language="en", duration=1.0)

    mocker.patch(
        "assemblix_api.external.voice.transcription.litellm.atranscription",
        side_effect=_fake_transcription,
    )

    # Act — first audio run.
    before = mock_llm.call_count
    run1 = await api_client.post(
        f"/api/workflows/{voice_setup.workflow_id}/execute/audio",
        files={"file": ("clip1.webm", b"fake-audio-1", "audio/webm")},
        data={"payload": json.dumps({"input": {}, "createSession": True})},
        headers=voice_setup.key_headers,
    )

    # Assert — completed, and the agent saw the first transcript as the user message.
    assert run1.status_code == 200
    assert run1.json()["status"] == "completed"
    agent_calls_1 = mock_llm.calls[before:]
    assert any(
        "first voice message" in json.dumps(c["messages"], default=str) for c in agent_calls_1
    )

    # Act — second audio run (fresh session).
    before = mock_llm.call_count
    run2 = await api_client.post(
        f"/api/workflows/{voice_setup.workflow_id}/execute/audio",
        files={"file": ("clip2.webm", b"fake-audio-2", "audio/webm")},
        data={"payload": json.dumps({"input": {}, "createSession": True})},
        headers=voice_setup.key_headers,
    )

    # Assert — completed, and the agent saw the second transcript.
    assert run2.status_code == 200
    assert run2.json()["status"] == "completed"
    agent_calls_2 = mock_llm.calls[before:]
    assert any(
        "second voice message" in json.dumps(c["messages"], default=str) for c in agent_calls_2
    )
