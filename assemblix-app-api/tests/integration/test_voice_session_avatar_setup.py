"""build_setup resolves the agent's avatar alongside its voice."""

from typing import Any

from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.services import voice_session_service as module
from assemblix_api.services.avatar_service import ResolvedAvatar


async def test_setup_carries_the_resolved_avatar(
    db_session: Any, auth_user: Any, voice_session_service: Any, monkeypatch
) -> None:
    resolved = ResolvedAvatar(provider="anam", api_key="k", avatar_id="av", avatar_model="cara-4")

    async def fake_resolve(avatar, *, project_id, credentials):
        assert avatar.avatar_id == "av"
        return resolved

    monkeypatch.setattr(module, "resolve_avatar", fake_resolve)
    agent = await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id,
        name="Face",
        config={
            "instructions": [{"role": "system", "content": "Answer calls."}],
            "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
            "avatar": {"provider": "anam", "avatarModel": "cara-4", "avatarId": "av"},
        },
    )

    setup = await voice_session_service.build_setup(
        voice_agent_id=agent.id, project_id=auth_user.project_id
    )

    assert setup.avatar == resolved


async def test_voice_only_setup_has_no_avatar(
    db_session: Any, auth_user: Any, voice_session_service: Any
) -> None:
    agent = await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id,
        name="Voice",
        config={
            "instructions": [{"role": "system", "content": "Answer calls."}],
            "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
        },
    )

    setup = await voice_session_service.build_setup(
        voice_agent_id=agent.id, project_id=auth_user.project_id
    )

    assert setup.avatar is None
