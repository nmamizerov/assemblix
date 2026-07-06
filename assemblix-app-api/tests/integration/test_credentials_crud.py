"""API CRUD tests for LLM credentials (user's own provider keys) — status only."""

from __future__ import annotations

import pytest_asyncio


async def _create_credential(client, headers, project_id, name="My OpenAI"):
    """Create an OpenAI credential and return the response."""
    return await client.post(
        "/api/credentials/",
        json={
            "type": "openai_token",
            "value": "sk-test-user-key",
            "name": name,
            "projectId": str(project_id),
        },
        headers=headers,
    )


@pytest_asyncio.fixture
async def credential(client, auth_user, auth_headers) -> str:
    """Per-test setup: create a credential and return its id (@BeforeEach)."""
    resp = await _create_credential(client, auth_headers, auth_user.project_id)
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_credentials(client, auth_user, auth_headers) -> None:
    """POST /api/credentials/ → 201."""
    # Arrange
    payload = {
        "type": "gemini_token",
        "value": "gm-test-user-key",
        "name": "My Gemini",
        "projectId": str(auth_user.project_id),
    }

    # Act
    resp = await client.post("/api/credentials/", json=payload, headers=auth_headers)

    # Assert
    assert resp.status_code == 201


async def test_get_credentials(client, auth_headers, credential) -> None:
    """GET /api/credentials/{id} → 200."""
    # Act
    resp = await client.get(f"/api/credentials/{credential}", headers=auth_headers)

    # Assert
    assert resp.status_code == 200


async def test_update_credentials(client, auth_headers, credential) -> None:
    """PATCH /api/credentials/{id} → 200."""
    # Act
    resp = await client.patch(
        f"/api/credentials/{credential}",
        json={"name": "Renamed key"},
        headers=auth_headers,
    )

    # Assert
    assert resp.status_code == 200


async def test_delete_credentials(client, auth_headers, credential) -> None:
    """DELETE /api/credentials/{id} → 204."""
    # Act
    resp = await client.delete(f"/api/credentials/{credential}", headers=auth_headers)

    # Assert
    assert resp.status_code == 204


async def test_create_elevenlabs_credential(client, auth_user, auth_headers) -> None:
    """POST /credentials with the new elevenlabs_token type → 201."""
    # Arrange
    payload = {
        "type": "elevenlabs_token",
        "value": "xi-secret",
        "name": "My ElevenLabs",
        "projectId": str(auth_user.project_id),
    }
    # Act
    resp = await client.post("/api/credentials/", json=payload, headers=auth_headers)
    # Assert
    assert resp.status_code == 201
    assert resp.json()["type"] == "elevenlabs_token"
