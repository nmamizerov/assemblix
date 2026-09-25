"""The session mint hands an avatar agent's caller a LiveKit room to join."""

from uuid import uuid4

import jwt
import pytest

from assemblix_api.core.settings import get_settings
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.realtime.session_token import mint_session_token, verify_session_token

_BASE = {
    "instructions": [{"role": "system", "content": "Answer calls."}],
    "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
}
_AVATAR = {
    "provider": "anam",
    "avatarModel": "cara-4",
    "avatarId": "av-1",
    "credentialId": str(uuid4()),
}
_SECRET = "s" * 32


@pytest.fixture
def livekit_on(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_url", "http://livekit:7880")
    monkeypatch.setattr(settings, "livekit_public_url", "wss://rtc.example.com")
    monkeypatch.setattr(settings, "livekit_api_key", "key")
    monkeypatch.setattr(settings, "livekit_api_secret", _SECRET)


async def _agent(db_session, auth_user, config: dict):
    return await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id, name="Face", config=config
    )


async def test_voice_only_agent_gets_no_media(client, db_session, auth_user, auth_headers) -> None:
    agent = await _agent(db_session, auth_user, _BASE)
    response = await client.post(f"/api/voice-agents/{agent.id}/sessions", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["media"] is None
    assert verify_session_token(body["token"]).room is None


async def test_avatar_agent_gets_a_room(
    client, db_session, auth_user, auth_headers, livekit_on
) -> None:
    agent = await _agent(db_session, auth_user, {**_BASE, "avatar": _AVATAR})
    response = await client.post(f"/api/voice-agents/{agent.id}/sessions", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    room = verify_session_token(body["token"]).room
    assert room is not None and room.startswith("va-")
    assert body["media"]["transport"] == "livekit"
    assert body["media"]["url"] == "wss://rtc.example.com"
    claims = jwt.decode(body["media"]["token"], _SECRET, algorithms=["HS256"])
    assert claims["sub"] == "user"
    assert claims["video"]["room"] == room


async def test_avatar_agent_without_livekit_is_a_400(
    client, db_session, auth_user, auth_headers
) -> None:
    agent = await _agent(db_session, auth_user, {**_BASE, "avatar": _AVATAR})
    response = await client.post(f"/api/voice-agents/{agent.id}/sessions", headers=auth_headers)
    assert response.status_code == 400


def test_room_claim_round_trips() -> None:
    token = mint_session_token(
        voice_agent_id=uuid4(), project_id=uuid4(), is_debug=True, room="va-abc"
    )
    assert verify_session_token(token).room == "va-abc"
