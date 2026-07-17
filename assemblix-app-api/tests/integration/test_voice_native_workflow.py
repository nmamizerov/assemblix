"""End-to-end test: audio-direct agent + transcribe→history (Task 9).

Exercises the real production path over HTTP — register → create API key → create
a workflow whose START accepts voice → publish → execute with an audio blob
(multipart). The STT seam (``litellm.atranscription``) is mocked and the LLM seam
is ``mock_llm``, so this test proves our own wiring, not the providers.

Graph shape — LINEAR, not a parallel fork: two separate START(audio)→…→END
workflows, one per branch:
  1. START(audio) → AGENT on an audio-capable Gemini model → END
     (proves the audio blob reaches the LLM as a content part, no transcription).
  2. START(audio) → transcribe (saveAsUserMessage) → END
     (proves the transcript is saved as the USER chat turn).

Deviation from the brief's parallel-fork sketch (start ⇉ [agent, transcribe] → end):
wiring that fork through the real ``/execute/audio`` HTTP path hits a genuine
concurrency bug in ``WorkflowExecutor._execution_loop_parallel`` — the transcribe
branch's ``chat_message_service.save_message`` DB write races the agent branch's
step-recording DB write on the *same* AsyncSession, raising
``sqlalchemy.exc.InvalidRequestError: This session is provisioning a new
connection; concurrent operations are not permitted``. That is a pre-existing
execution-engine limitation (concurrent branches sharing one session), out of
scope for the voice feature itself. Per the task brief's escalation guidance, this
test falls back to two linear graphs that independently prove both behaviors.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from tests.fixtures.workflows import agent_config, edge, node

# Gemini model with capabilities.accepts_audio=True in the model catalog
# (see tests/unit/external/test_model_catalog_audio.py).
AUDIO_MODEL = "gemini-3-flash-preview"

# WAV, not webm: the audio-direct agent sends the raw blob to pydantic_ai's
# BinaryContent, whose audio-format lookup only covers a fixed set of mime types
# (wav/mp3/flac/ogg/aiff/aac) — see agent_node.py's audio_part construction.
AUDIO_FILE = ("clip.wav", b"RIFFfake-audio", "audio/wav")


def _start_config() -> dict[str, Any]:
    return {"acceptVoice": True, "voiceModel": {"provider": "openai", "model": "whisper-1"}}


def _audio_agent_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """START (accepts voice) → AGENT on an audio-capable model → END."""
    nodes = [
        node("start", "start", _start_config()),
        node(
            "agent",
            "agent",
            agent_config(provider="gemini", model=AUDIO_MODEL, instructions="Reply to the user."),
        ),
        node("end", "end", {}),
    ]
    edges = [edge("start", "agent"), edge("agent", "end")]
    return nodes, edges


def _transcribe_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """START (accepts voice) → transcribe (saves as USER turn) → END."""
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
        node("end", "end", {}),
    ]
    edges = [edge("start", "transcribe"), edge("transcribe", "end")]
    return nodes, edges


async def _register_and_publish(
    api_client, *, email: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> SimpleNamespace:
    """Register a user, mint an API key, create + publish a workflow."""
    reg = await api_client.post("/api/auth/register", json={"email": email, "password": "pass1234"})
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "voice-native-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    create_resp = await api_client.post(
        "/api/workflows/",
        json={
            "projectId": project_id,
            "name": "Voice native workflow",
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


def _content_parts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten any list-typed ``content`` across messages into a flat list of parts."""
    parts: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            parts.extend(p for p in content if isinstance(p, dict))
    return parts


async def test_audio_direct_agent_receives_audio_content_part(api_client, mock_llm) -> None:
    """START(audio) → AGENT(audio-capable model) → END: the agent's LLM call
    carries a raw audio content part instead of a transcribed text message."""
    # Arrange
    mock_llm.set_response("agent reply")
    nodes, edges = _audio_agent_workflow()
    setup = await _register_and_publish(
        api_client, email="voice-agent@example.com", nodes=nodes, edges=edges
    )

    # Act
    before = mock_llm.call_count
    run = await api_client.post(
        f"/api/workflows/{setup.workflow_id}/execute/audio",
        files={"file": AUDIO_FILE},
        data={"payload": json.dumps({"input": {}, "createSession": True})},
        headers=setup.key_headers,
    )

    # Assert — run completed and the LLM call carried an audio content part.
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    agent_calls = mock_llm.calls[before:]
    assert agent_calls, "expected at least one LLM call from the audio-direct agent"
    parts = [p for c in agent_calls for p in _content_parts(c["messages"])]
    assert any(p.get("type") in {"input_audio", "audio", "file"} for p in parts), (
        f"no audio content part found in agent messages: {parts}"
    )


async def test_transcribe_node_saves_transcript_as_user_turn(
    api_client, mock_llm, mocker: Any
) -> None:
    """START(audio) → transcribe(saveAsUserMessage) → END: the transcript from
    the (mocked) STT call is saved as the USER turn in chat history."""

    # Arrange — patch the STT seam so the branch is deterministic.
    async def _fake_transcription(**_: Any) -> SimpleNamespace:
        return SimpleNamespace(text="native voice transcript", language="en", duration=1.0)

    mocker.patch(
        "assemblix_api.external.voice.transcription.litellm.atranscription",
        side_effect=_fake_transcription,
    )
    nodes, edges = _transcribe_workflow()
    setup = await _register_and_publish(
        api_client, email="voice-transcribe@example.com", nodes=nodes, edges=edges
    )

    # Act
    run = await api_client.post(
        f"/api/workflows/{setup.workflow_id}/execute/audio",
        files={"file": AUDIO_FILE},
        data={"payload": json.dumps({"input": {}, "createSession": True})},
        headers=setup.key_headers,
    )

    # Assert — run completed and the transcript was saved as a USER chat turn.
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    session_id = body["sessionId"]
    detail = await api_client.get(f"/api/chat-sessions/{session_id}", headers=setup.jwt_headers)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    user_messages = [m for m in messages if m["role"] == "user"]
    assert any(m["content"] == "native voice transcript" for m in user_messages), (
        f"expected a saved user turn with the transcript, got: {user_messages}"
    )
