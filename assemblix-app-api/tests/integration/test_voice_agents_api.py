"""Voice Agent REST API."""

from typing import Any


def _config(**overrides: Any) -> dict:
    """A minimal valid voice-agent config in wire (camelCase) form."""
    config = {
        "instructions": [{"role": "system", "content": "You are a clinic receptionist."}],
        "knowledgeBaseIds": [],
        "firstMessage": "Hello, how can I help?",
        "language": "ru",
        "voice": {
            "provider": "openai",
            "model": "gpt-realtime-2.1",
            "voiceId": "alloy",
            "credentialId": None,
            "realtime": False,
        },
        "params": {"vadSilenceMs": 500},
    }
    config.update(overrides)
    return config


async def test_voice_agent_lifecycle(client, auth_user, auth_headers) -> None:
    """Create → list → get → patch → delete, with the JSONB config round-tripping intact."""
    # Arrange
    payload = {
        "projectId": str(auth_user.project_id),
        "name": "Clinic receptionist",
        "description": "Answers calls",
        "config": _config(),
    }

    # Act — create
    created = await client.post("/api/voice-agents/", json=payload, headers=auth_headers)

    # Assert — create
    assert created.status_code == 201
    body = created.json()
    agent_id = body["id"]
    assert body["name"] == "Clinic receptionist"
    assert body["projectId"] == str(auth_user.project_id)
    assert body["config"]["voice"]["model"] == "gpt-realtime-2.1"
    assert body["config"]["params"] == {"vadSilenceMs": 500}
    assert body["config"]["instructions"][0]["content"] == "You are a clinic receptionist."

    # Act — list
    listed = await client.get(
        "/api/voice-agents/", params={"project_id": str(auth_user.project_id)}, headers=auth_headers
    )

    # Assert — list
    assert listed.status_code == 200
    assert [a["id"] for a in listed.json()] == [agent_id]

    # Act — get
    fetched = await client.get(f"/api/voice-agents/{agent_id}", headers=auth_headers)

    # Assert — get
    assert fetched.status_code == 200
    assert fetched.json()["config"]["firstMessage"] == "Hello, how can I help?"

    # Act — patch name only
    patched = await client.patch(
        f"/api/voice-agents/{agent_id}", json={"name": "Renamed"}, headers=auth_headers
    )

    # Assert — patch leaves the untouched config alone
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"
    assert patched.json()["config"]["voice"]["model"] == "gpt-realtime-2.1"

    # Act — patch config, attaching the analysis hooks
    reconfigured = await client.patch(
        f"/api/voice-agents/{agent_id}",
        json={"config": _config(turnWorkflowId="a0000000-0000-0000-0000-000000000001")},
        headers=auth_headers,
    )

    # Assert — hooks persist, name is untouched
    assert reconfigured.status_code == 200
    assert reconfigured.json()["config"]["turnWorkflowId"] == "a0000000-0000-0000-0000-000000000001"
    assert reconfigured.json()["name"] == "Renamed"

    # Act — delete
    deleted = await client.delete(f"/api/voice-agents/{agent_id}", headers=auth_headers)

    # Assert — delete removes it from the listing
    assert deleted.status_code == 204
    remaining = await client.get(
        "/api/voice-agents/", params={"project_id": str(auth_user.project_id)}, headers=auth_headers
    )
    assert remaining.json() == []
