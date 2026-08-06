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


async def test_voice_agent_rejects_invalid_config(client, auth_user, auth_headers) -> None:
    """A non-conversation model is a 400; an empty prompt is a 422 from the schema."""
    # Arrange
    not_a_conversation_model = _config(
        voice={
            "provider": "yandex",
            "model": "yandex-tts-v3",
            "voiceId": "alena",
            "credentialId": None,
            "realtime": True,
        }
    )
    empty_prompt = _config(instructions=[])

    # Act
    bad_model = await client.post(
        "/api/voice-agents/",
        json={
            "projectId": str(auth_user.project_id),
            "name": "A",
            "config": not_a_conversation_model,
        },
        headers=auth_headers,
    )
    no_prompt = await client.post(
        "/api/voice-agents/",
        json={"projectId": str(auth_user.project_id), "name": "B", "config": empty_prompt},
        headers=auth_headers,
    )

    # Assert
    assert bad_model.status_code == 400
    assert "conversation" in bad_model.json()["detail"].lower()
    assert no_prompt.status_code == 422

    # Assert — a rejected create persists nothing
    listed = await client.get(
        "/api/voice-agents/", params={"project_id": str(auth_user.project_id)}, headers=auth_headers
    )
    assert listed.json() == []


async def test_voice_agent_is_scoped_to_its_project(
    client, auth_user, auth_headers, user_factory
) -> None:
    """An agent is invisible and unreachable outside its own project, and to anonymous callers."""
    # Arrange
    created = await client.post(
        "/api/voice-agents/",
        json={"projectId": str(auth_user.project_id), "name": "Private", "config": _config()},
        headers=auth_headers,
    )
    agent_id = created.json()["id"]
    outsider = await user_factory()
    outsider_headers = {"Authorization": f"Bearer {outsider.token}"}

    # Act
    foreign_get = await client.get(f"/api/voice-agents/{agent_id}", headers=outsider_headers)
    foreign_list = await client.get(
        "/api/voice-agents/",
        params={"project_id": str(auth_user.project_id)},
        headers=outsider_headers,
    )
    anonymous = await client.get(f"/api/voice-agents/{agent_id}")

    # Assert
    assert foreign_get.status_code in (403, 404)
    assert foreign_list.status_code in (403, 404)
    assert anonymous.status_code == 401

    # Assert — the outsider's own project is simply empty, not broken
    own = await client.get(
        "/api/voice-agents/",
        params={"project_id": str(outsider.project_id)},
        headers=outsider_headers,
    )
    assert own.status_code == 200
    assert own.json() == []
