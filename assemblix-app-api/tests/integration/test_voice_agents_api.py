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


async def _create_workflow(client, project_id: str, headers: dict, name: str = "Hook") -> str:
    """Create an empty workflow and return its id."""
    response = await client.post(
        "/api/workflows/",
        json={"projectId": project_id, "name": name, "nodes": [], "edges": []},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


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
    workflow_id = await _create_workflow(client, str(auth_user.project_id), auth_headers)
    reconfigured = await client.patch(
        f"/api/voice-agents/{agent_id}",
        json={"config": _config(turnWorkflowId=workflow_id)},
        headers=auth_headers,
    )

    # Assert — hooks persist, name is untouched
    assert reconfigured.status_code == 200
    assert reconfigured.json()["config"]["turnWorkflowId"] == workflow_id
    assert reconfigured.json()["name"] == "Renamed"

    # Act — clear the description with an explicit null
    cleared = await client.patch(
        f"/api/voice-agents/{agent_id}", json={"description": None}, headers=auth_headers
    )

    # Assert — an explicit null clears, an omitted field does not
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None
    kept = await client.patch(
        f"/api/voice-agents/{agent_id}", json={"name": "Renamed again"}, headers=auth_headers
    )
    assert kept.json()["description"] is None

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


async def test_voice_agent_rejects_hook_workflow_from_another_project(
    client, auth_user, auth_headers, user_factory
) -> None:
    """Analysis hooks may not point at a workflow owned by a different project."""
    # Arrange
    outsider = await user_factory()
    outsider_headers = {"Authorization": f"Bearer {outsider.token}"}
    foreign_workflow_id = await _create_workflow(
        client, str(outsider.project_id), outsider_headers, name="Foreign"
    )
    own_workflow_id = await _create_workflow(client, str(auth_user.project_id), auth_headers)

    # Act — create with a foreign hook, then create a legitimate agent and try to patch it
    rejected_create = await client.post(
        "/api/voice-agents/",
        json={
            "projectId": str(auth_user.project_id),
            "name": "Leaky",
            "config": _config(finalWorkflowId=foreign_workflow_id),
        },
        headers=auth_headers,
    )
    created = await client.post(
        "/api/voice-agents/",
        json={
            "projectId": str(auth_user.project_id),
            "name": "Legit",
            "config": _config(turnWorkflowId=own_workflow_id),
        },
        headers=auth_headers,
    )
    rejected_patch = await client.patch(
        f"/api/voice-agents/{created.json()['id']}",
        json={"config": _config(turnWorkflowId=foreign_workflow_id)},
        headers=auth_headers,
    )

    # Assert — cross-project hooks are refused on both paths, same-project ones are fine
    assert rejected_create.status_code == 400
    assert "does not belong to this project" in rejected_create.json()["detail"]
    assert created.status_code == 201
    assert rejected_patch.status_code == 400

    # Assert — the rejected create persisted nothing and the patch left the hook intact
    listed = await client.get(
        "/api/voice-agents/", params={"project_id": str(auth_user.project_id)}, headers=auth_headers
    )
    assert [a["name"] for a in listed.json()] == ["Legit"]
    assert listed.json()[0]["config"]["turnWorkflowId"] == own_workflow_id


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
