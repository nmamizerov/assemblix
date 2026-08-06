"""Integration tests for capability-filtered voice discovery endpoints."""

from __future__ import annotations

from assemblix_api.core.settings import get_settings
from assemblix_api.external.voice import yandex as yandex_voice


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

    async def _fake_list(api_key, *, search=None):
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
    """A credential type with no voice catalog (deepseek) → 400."""
    # Arrange
    cred_id = await _create_eleven_credential(
        client, auth_user, auth_headers, cred_type="deepseek_token"
    )
    mocker.patch("assemblix_api.api.rest.voice.list_voices")
    # Act
    resp = await client.get(f"/api/voice/credentials/{cred_id}/voices", headers=auth_headers)
    # Assert
    assert resp.status_code == 400


async def test_conversation_voices_for_openai_and_gemini(client, auth_user, auth_headers) -> None:
    """OpenAI/Gemini conversation voices are served, existing providers stay intact.

    Covers: system-voices returns the 7 OpenAI ids and 8 Gemini ids; none of the
    TTS-only OpenAI ids leak in; the credential-scoped endpoint returns the same
    catalogs for openai_token/gemini_token credentials; yandex system-voices still
    returns its own catalog; an unregistered provider still 404s.
    """
    # Arrange
    openai_ids = {"alloy", "echo", "sage", "shimmer", "verse", "marin", "cedar"}
    tts_only_ids = {"ash", "ballad", "coral", "fable", "onyx", "nova"}
    gemini_ids = {"Puck", "Charon", "Kore", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr"}
    openai_cred_id = await _create_eleven_credential(
        client, auth_user, auth_headers, cred_type="openai_token"
    )
    gemini_cred_id = await _create_eleven_credential(
        client, auth_user, auth_headers, cred_type="gemini_token"
    )

    # Act
    openai_system_resp = await client.get(
        "/api/voice/providers/openai/system-voices", headers=auth_headers
    )
    gemini_system_resp = await client.get(
        "/api/voice/providers/gemini/system-voices", headers=auth_headers
    )
    openai_cred_resp = await client.get(
        f"/api/voice/credentials/{openai_cred_id}/voices", headers=auth_headers
    )
    gemini_cred_resp = await client.get(
        f"/api/voice/credentials/{gemini_cred_id}/voices", headers=auth_headers
    )
    yandex_system_resp = await client.get(
        "/api/voice/providers/yandex/system-voices", headers=auth_headers
    )
    unregistered_resp = await client.get(
        "/api/voice/providers/does-not-exist/system-voices", headers=auth_headers
    )

    # Assert
    assert openai_system_resp.status_code == 200
    assert {v["id"] for v in openai_system_resp.json()} == openai_ids
    assert not (tts_only_ids & {v["id"] for v in openai_system_resp.json()})
    assert gemini_system_resp.status_code == 200
    assert {v["id"] for v in gemini_system_resp.json()} == gemini_ids
    assert openai_cred_resp.status_code == 200
    assert {v["id"] for v in openai_cred_resp.json()} == openai_ids
    assert gemini_cred_resp.status_code == 200
    assert {v["id"] for v in gemini_cred_resp.json()} == gemini_ids
    assert yandex_system_resp.status_code == 200
    assert {v["id"] for v in yandex_system_resp.json()} == {
        v.id for v in yandex_voice.list_voices()
    }
    assert unregistered_resp.status_code == 404


async def test_system_voices_lists_platform_voices(
    client, auth_headers, monkeypatch, mocker
) -> None:
    """GET /voice/providers/elevenlabs/system-voices returns the platform's voices."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")

    async def _fake_list(api_key, *, search=None):
        from assemblix_api.external.voice.elevenlabs import ElevenLabsVoice

        return [ElevenLabsVoice(id="sv1", name="Platform Voice")]

    mocker.patch("assemblix_api.api.rest.voice.list_voices", side_effect=_fake_list)
    # Act
    resp = await client.get("/api/voice/providers/elevenlabs/system-voices", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "sv1"


async def test_system_voices_503_when_unset(client, auth_headers, monkeypatch) -> None:
    """No system ElevenLabs key configured → 503."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "")
    # Act
    resp = await client.get("/api/voice/providers/elevenlabs/system-voices", headers=auth_headers)
    # Assert
    assert resp.status_code == 503


async def test_system_voices_404_for_other_provider(client, auth_headers) -> None:
    """A provider with no voice catalog at all has no system voices → 404."""
    # Act
    resp = await client.get("/api/voice/providers/deepseek/system-voices", headers=auth_headers)
    # Assert
    assert resp.status_code == 404
