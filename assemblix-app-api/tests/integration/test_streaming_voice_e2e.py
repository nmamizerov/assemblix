"""E2E: streaming voice emits AUDIO_DELTA frames on the inline debug SSE, ordered before the
agent's step_complete. The ElevenLabs WS is faked; no network."""

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.engine import get_async_engine
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from assemblix_api.external.voice.realtime import RealtimeTTSSession
from tests.fixtures.workflows import agent_config, edge, node


def _sse_frames(text: str) -> list[dict]:
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


def _voice_stream_workflow() -> tuple[list[dict], list[dict]]:
    voice_agent = agent_config(instructions="Reply.")
    voice_agent["stream"] = True
    voice_agent["output_type"] = "voice"
    voice_agent["voice"] = {"provider": "elevenlabs", "model": "eleven_flash_v2_5", "voiceId": "v1"}
    nodes = [
        node("start", "start", {}),
        node("agent", "agent", voice_agent),
        node("end", "end", {}),
    ]
    return nodes, [edge("start", "agent"), edge("agent", "end")]


async def _setup(api_client) -> SimpleNamespace:
    reg = await api_client.post(
        "/api/auth/register", json={"email": "voice-e2e@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]
    org_id = reg.json()["organizationId"]
    key_resp = await api_client.post(
        "/api/api-keys/", json={"projectId": project_id, "name": "k"}, headers=jwt
    )
    key = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}
    nodes, edges = _voice_stream_workflow()
    create = await api_client.post(
        "/api/workflows/",
        json={"projectId": project_id, "name": "Voice stream", "nodes": nodes, "edges": edges},
        headers=jwt,
    )
    workflow_id = create.json()["id"]
    await api_client.post(f"/api/workflows/{workflow_id}/publish", headers=jwt)
    async with AsyncSession(get_async_engine()) as session:
        org_repo = OrganizationRepository(session)
        org = await org_repo.get_by_id(org_id)
        org.plan = "pro"
        org.credits_balance = Decimal("1000000")
        await org_repo.update(org)
        await session.commit()
    return SimpleNamespace(key=key, workflow_id=workflow_id)


async def test_streaming_voice_emits_audio_before_agent_step_complete(
    api_client, mock_llm, mock_tts_ws, mocker, monkeypatch
) -> None:
    """A streaming voice run carries audio_delta frames, all before the agent's step_complete."""
    # Arrange
    from assemblix_api.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    mock_llm.set_stream(["Hi ", "there."])
    mock_tts_ws.script_audio([(b"\x01\x02", None), (b"\x03\x04", None)])
    mocker.patch(
        "assemblix_api.nodes.agent_voice.RealtimeTTSSession",
        lambda **kw: RealtimeTTSSession(**{**kw, "connect": mock_tts_ws.connect}),
    )
    setup = await _setup(api_client)

    # Act
    resp = await asyncio.wait_for(
        api_client.post(
            f"/api/workflows/{setup.workflow_id}/execute/debug",
            json={"input": {"message": "hi"}, "stream": True},
            headers=setup.key,
        ),
        timeout=30.0,
    )

    # Assert
    assert resp.status_code == 200
    frames = _sse_frames(resp.text)
    types = [f["event"] for f in frames]
    assert "audio_delta" in types
    assert "execution_complete" in types

    def _node_type(f: dict) -> str | None:
        # The inline SSE serializes the whole DebugEvent, so the step payload is nested.
        inner = (f["data"] or {}).get("data") or {}
        return inner.get("node_type") or inner.get("nodeType")

    last_audio = max(i for i, f in enumerate(frames) if f["event"] == "audio_delta")
    agent_complete = next(
        i
        for i, f in enumerate(frames)
        if f["event"] == "step_complete" and _node_type(f) == "agent"
    )
    assert last_audio < agent_complete


async def test_non_stream_voice_has_no_audio_delta(
    api_client, mock_llm, mocker, monkeypatch
) -> None:
    """Without stream=true the same workflow emits no audio_delta (buffered path)."""
    # Arrange
    from assemblix_api.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    mock_llm.set_response("Hi there.")
    ws = mocker.patch("assemblix_api.nodes.agent_voice.RealtimeTTSSession")
    setup = await _setup(api_client)

    # Act
    resp = await asyncio.wait_for(
        api_client.post(
            f"/api/workflows/{setup.workflow_id}/execute/debug",
            json={"input": {"message": "hi"}},
            headers=setup.key,
        ),
        timeout=30.0,
    )

    # Assert
    assert resp.status_code == 200
    assert "event: audio_delta" not in resp.text
    ws.assert_not_called()
