"""Half-cascade configuration: what a call resolves to, and what it refuses."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from assemblix_api.core.settings import get_settings
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.services.voice_session_service import VoiceSessionService

_ELEVENLABS_STREAMING = {
    "provider": "elevenlabs",
    "model": "eleven_flash_v2_5",
    "voiceId": "v1",
    "credentialId": None,
    "realtime": True,
}


async def _agent(db_session: Any, project_id: Any, **config: Any) -> Any:
    return await VoiceAgentRepository(db_session).create(
        project_id=project_id,
        name="Receptionist",
        config={
            "instructions": [{"role": "system", "content": "Answer calls."}],
            "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
            **config,
        },
    )


async def test_setup_resolves_the_tts_target_and_falls_back_to_the_system_key(
    db_session: Any,
    auth_user: Any,
    voice_session_service: VoiceSessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An agent configured with an external voice resolves a synthesis target
    alongside the model, using the platform key when the author supplied none,
    while an agent without one resolves nothing extra."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    with_tts = await _agent(db_session, auth_user.project_id, tts=_ELEVENLABS_STREAMING)
    without_tts = await _agent(db_session, auth_user.project_id)

    # Act
    cascaded = await voice_session_service.build_setup(
        voice_agent_id=with_tts.id, project_id=auth_user.project_id
    )
    native = await voice_session_service.build_setup(
        voice_agent_id=without_tts.id, project_id=auth_user.project_id
    )

    # Assert
    assert cascaded.tts is not None
    assert (cascaded.tts.provider, cascaded.tts.model) == ("elevenlabs", "eleven_flash_v2_5")
    assert cascaded.tts.voice_id == "v1"
    assert cascaded.tts.api_key == "xi-system"
    assert cascaded.tts.uses_system_key is True
    assert native.tts is None


async def test_setup_refuses_a_voice_the_stack_cannot_actually_speak(
    db_session: Any,
    auth_user: Any,
    voice_session_service: VoiceSessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that cannot answer in text, and a voice model with no streaming
    route, both fail when the call is set up rather than on the first reply."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    no_text_output = await _agent(
        db_session,
        auth_user.project_id,
        voice={"provider": "openai", "model": "not-a-text-answering-model", "voiceId": "alloy"},
        tts=_ELEVENLABS_STREAMING,
    )
    no_realtime_route = await _agent(
        db_session,
        auth_user.project_id,
        tts={**_ELEVENLABS_STREAMING, "model": "eleven_multilingual_v2"},
    )

    # Act / Assert
    with pytest.raises(HTTPException) as text_error:
        await voice_session_service.build_setup(
            voice_agent_id=no_text_output.id, project_id=auth_user.project_id
        )
    with pytest.raises(HTTPException) as route_error:
        await voice_session_service.build_setup(
            voice_agent_id=no_realtime_route.id, project_id=auth_user.project_id
        )

    assert text_error.value.status_code == 400
    assert route_error.value.status_code == 400
