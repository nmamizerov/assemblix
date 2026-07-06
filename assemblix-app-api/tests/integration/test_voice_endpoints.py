"""Integration tests for capability-filtered voice discovery endpoints."""

from __future__ import annotations


async def test_speech_providers_include_elevenlabs(client, auth_headers) -> None:
    """GET /voice/providers?capability=speech lists elevenlabs."""
    # Arrange / Act
    resp = await client.get("/api/voice/providers?capability=speech", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert any(p["name"] == "elevenlabs" for p in resp.json())


async def test_speech_models_for_elevenlabs(client, auth_headers) -> None:
    """GET /voice/providers/elevenlabs/models?capability=speech returns speech models."""
    # Arrange / Act
    resp = await client.get(
        "/api/voice/providers/elevenlabs/models?capability=speech", headers=auth_headers
    )
    # Assert
    assert resp.status_code == 200
    assert any(m["id"] == "eleven_multilingual_v2" for m in resp.json())


async def _create_eleven_credential(client, auth_user, auth_headers, cred_type="elevenlabs_token"):
    resp = await client.post(
        "/api/credentials/",
        json={
            "type": cred_type,
            "value": "xi-secret",
            "name": "c",
            "projectId": str(auth_user.project_id),
        },
        headers=auth_headers,
    )
    return resp.json()["id"]


async def test_list_credential_voices(client, auth_user, auth_headers, mocker) -> None:
    """GET /voice/credentials/{id}/voices returns the account's voices."""
    # Arrange
    cred_id = await _create_eleven_credential(client, auth_user, auth_headers)

    async def _fake_list(api_key):
        from assemblix_api.external.voice.elevenlabs import ElevenLabsVoice

        return [ElevenLabsVoice(id="v1", name="Rachel")]

    mocker.patch("assemblix_api.api.rest.voice.list_voices", side_effect=_fake_list)
    # Act
    resp = await client.get(f"/api/voice/credentials/{cred_id}/voices", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "v1"
    assert resp.json()[0]["name"] == "Rachel"


async def test_list_credential_voices_wrong_type_rejected(
    client, auth_user, auth_headers, mocker
) -> None:
    """A non-elevenlabs credential → 400."""
    # Arrange
    cred_id = await _create_eleven_credential(
        client, auth_user, auth_headers, cred_type="openai_token"
    )
    mocker.patch("assemblix_api.api.rest.voice.list_voices")
    # Act
    resp = await client.get(f"/api/voice/credentials/{cred_id}/voices", headers=auth_headers)
    # Assert
    assert resp.status_code == 400
