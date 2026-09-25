"""An avatar on a voice agent is validated when the agent is saved."""

from typing import Any

import pytest

from assemblix_api.core.settings import get_settings


def _config(**overrides: Any) -> dict:
    config = {
        "instructions": [{"role": "system", "content": "You are a receptionist."}],
        "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
    }
    config.update(overrides)
    return config


_AVATAR = {
    "provider": "anam",
    "avatarModel": "cara-4",
    "avatarId": "11111111-1111-1111-1111-111111111111",
    "credentialId": "22222222-2222-2222-2222-222222222222",
}


@pytest.fixture
def livekit_on(monkeypatch) -> None:
    settings = get_settings()
    for field in ("livekit_url", "livekit_public_url", "livekit_api_key", "livekit_api_secret"):
        monkeypatch.setattr(settings, field, "x")


async def _create(client, auth_user, auth_headers, config: dict):
    return await client.post(
        "/api/voice-agents/",
        json={"projectId": str(auth_user.project_id), "name": "Face", "config": config},
        headers=auth_headers,
    )


async def test_avatar_requires_livekit(client, auth_user, auth_headers) -> None:
    response = await _create(client, auth_user, auth_headers, _config(avatar=_AVATAR))
    assert response.status_code == 400
    assert "LiveKit" in response.json()["detail"]


async def test_avatar_requires_avatar_and_credential(
    client, auth_user, auth_headers, livekit_on
) -> None:
    response = await _create(
        client, auth_user, auth_headers, _config(avatar={**_AVATAR, "avatarId": None})
    )
    assert response.status_code == 400


async def test_avatar_requires_avatar_model(client, auth_user, auth_headers, livekit_on) -> None:
    # Arrange
    config = _config(avatar={**_AVATAR, "avatarModel": ""})

    # Act
    response = await _create(client, auth_user, auth_headers, config)

    # Assert
    assert response.status_code == 400


async def test_avatar_rejects_unknown_provider(client, auth_user, auth_headers, livekit_on) -> None:
    response = await _create(
        client, auth_user, auth_headers, _config(avatar={**_AVATAR, "provider": "nobody"})
    )
    assert response.status_code == 400


async def test_avatar_round_trips(client, auth_user, auth_headers, livekit_on) -> None:
    response = await _create(client, auth_user, auth_headers, _config(avatar=_AVATAR))
    assert response.status_code == 201, response.text
    assert response.json()["config"]["avatar"]["avatarId"] == _AVATAR["avatarId"]


async def test_no_avatar_needs_no_livekit(client, auth_user, auth_headers) -> None:
    response = await _create(client, auth_user, auth_headers, _config())
    assert response.status_code == 201, response.text
    assert response.json()["config"]["avatar"] is None
