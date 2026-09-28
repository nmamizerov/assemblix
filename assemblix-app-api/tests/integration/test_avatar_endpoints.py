"""Integration tests for avatar discovery + workflow session-mint endpoints."""

from __future__ import annotations

from uuid import uuid4

from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.repositories.credentials_repository import CredentialsRepository
from assemblix_api.database.repositories.workflow_repository import WorkflowRepository


async def _make_credential(
    db_session, project_id, *, cred_type=CredentialsType.ANAM_TOKEN, value="anam-key"
):
    """Create a credential directly via the repository (it encrypts the value on create)."""
    return await CredentialsRepository(db_session).create(
        project_id=project_id,
        type=cred_type,
        name="test-cred",
        value=value,
    )


async def _make_workflow(db_session, project_id, *, config=None):
    return await WorkflowRepository(db_session).create(
        project_id=project_id,
        slug=f"avatar-test-{uuid4()}",
        name="Avatar Test Workflow",
        config=config or {},
    )


async def test_list_providers(client, auth_headers) -> None:
    """GET /api/avatar/providers lists the anam provider."""
    # Act
    resp = await client.get("/api/avatar/providers", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert any(p["name"] == "anam" for p in resp.json())


async def test_list_credential_avatars(client, auth_user, auth_headers, mocker, db_session) -> None:
    """GET /api/avatar/credentials/{id}/avatars returns the account's avatars."""
    # Arrange
    cred = await _make_credential(db_session, auth_user.project_id)

    async def _fake(api_key):
        assert api_key == "anam-key"
        from assemblix_api.external.avatar.anam import AnamAvatar

        return [AnamAvatar(id="a1", name="Cara")]

    mocker.patch("assemblix_api.external.avatar.anam.list_avatars", side_effect=_fake)
    # Act
    resp = await client.get(f"/api/avatar/credentials/{cred.id}/avatars", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert resp.json() == [{"id": "a1", "name": "Cara"}]


async def test_list_credential_voices(client, auth_user, auth_headers, mocker, db_session) -> None:
    """GET /api/avatar/credentials/{id}/voices forwards the search term and maps voices."""
    # Arrange
    cred = await _make_credential(db_session, auth_user.project_id)
    captured = {}

    async def _fake(api_key, *, search=None):
        assert api_key == "anam-key"
        captured["search"] = search
        from assemblix_api.external.avatar.anam import AnamVoice

        return [AnamVoice(id="v1", name="Aurora")]

    mocker.patch("assemblix_api.external.avatar.anam.list_voices", side_effect=_fake)
    # Act
    resp = await client.get(
        f"/api/avatar/credentials/{cred.id}/voices?search=aur", headers=auth_headers
    )
    # Assert
    assert resp.status_code == 200
    assert resp.json() == [{"id": "v1", "name": "Aurora"}]
    assert captured["search"] == "aur"


async def test_mint_workflow_session(client, auth_user, auth_headers, mocker, db_session) -> None:
    """A selected avatar mints an audio-passthrough persona (face only, no anam voice/LLM)."""
    # Arrange
    cred = await _make_credential(db_session, auth_user.project_id)
    wf = await _make_workflow(
        db_session,
        auth_user.project_id,
        config={
            "avatar": {
                "provider": "anam",
                "avatarModel": "cara-4",
                "avatarId": "avatar-uuid",
                "credentialId": str(cred.id),
            }
        },
    )

    captured = {}

    async def _fake_mint(**kwargs):
        assert kwargs["api_key"] == "anam-key"
        captured["persona"] = kwargs["persona_config"]
        return "sess-xyz"

    mocker.patch("assemblix_api.services.avatar_service.mint_session", side_effect=_fake_mint)
    # Act
    resp = await client.post(f"/api/workflows/{wf.id}/avatar/session", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "anam"
    assert body["sessionToken"] == "sess-xyz"
    # Audio passthrough: the persona renders only the face and lip-syncs to our own audio,
    # so it carries no anam voiceId / llmId.
    assert captured["persona"]["avatarId"] == "avatar-uuid"
    assert captured["persona"]["enableAudioPassthrough"] is True
    assert "voiceId" not in captured["persona"]
    assert "llmId" not in captured["persona"]


async def test_mint_session_400_when_no_avatar_config(
    client, auth_user, auth_headers, db_session
) -> None:
    """A workflow with no avatar config → 400."""
    # Arrange
    wf = await _make_workflow(db_session, auth_user.project_id, config={})
    # Act
    resp = await client.post(f"/api/workflows/{wf.id}/avatar/session", headers=auth_headers)
    # Assert
    assert resp.status_code == 400


async def test_mint_session_400_when_avatar_missing(
    client, auth_user, auth_headers, db_session
) -> None:
    """An avatar config without a selected avatarId → 400 (a voice is no longer required)."""
    # Arrange
    cred = await _make_credential(db_session, auth_user.project_id)
    wf = await _make_workflow(
        db_session,
        auth_user.project_id,
        config={
            "avatar": {
                "provider": "anam",
                "avatarModel": "cara-4",
                "credentialId": str(cred.id),
            }
        },
    )
    # Act
    resp = await client.post(f"/api/workflows/{wf.id}/avatar/session", headers=auth_headers)
    # Assert
    assert resp.status_code == 400


async def test_providers_say_which_work_in_workflows(client, auth_headers) -> None:
    # Act
    resp = await client.get("/api/avatar/providers", headers=auth_headers)
    # Assert
    flags = {p["name"]: p["supportsWorkflow"] for p in resp.json()}
    assert flags["anam"] is True
    assert flags["bithuman"] is False


async def test_mint_session_400_for_a_voice_agent_only_provider(
    client, auth_user, auth_headers, db_session
) -> None:
    # Arrange
    cred = await _make_credential(
        db_session, auth_user.project_id, cred_type=CredentialsType.BITHUMAN_TOKEN, value="bh"
    )
    wf = await _make_workflow(
        db_session,
        auth_user.project_id,
        config={
            "avatar": {
                "provider": "bithuman",
                "avatarModel": "essence-2",
                "avatarId": "A1",
                "credentialId": str(cred.id),
            }
        },
    )
    # Act
    resp = await client.post(f"/api/workflows/{wf.id}/avatar/session", headers=auth_headers)
    # Assert
    assert resp.status_code == 400


async def test_bithuman_avatars_are_filtered_by_model(
    client, auth_user, auth_headers, mocker, db_session
) -> None:
    # Arrange
    from assemblix_api.external.avatar.bithuman import BithumanAvatar

    cred = await _make_credential(
        db_session, auth_user.project_id, cred_type=CredentialsType.BITHUMAN_TOKEN, value="bh"
    )

    async def _fake(api_key):
        assert api_key == "bh"
        return [
            BithumanAvatar(id="A1", name="Pup", supported_models=["essence-2"]),
            BithumanAvatar(id="A2", name="Owl", supported_models=["expression-2"]),
        ]

    mocker.patch("assemblix_api.external.avatar.bithuman.list_avatars", side_effect=_fake)
    url = f"/api/avatar/credentials/{cred.id}/avatars"

    # Act
    everything = await client.get(url, headers=auth_headers)
    filtered = await client.get(url, params={"model": "expression-2"}, headers=auth_headers)

    # Assert
    assert [a["id"] for a in everything.json()] == ["A1", "A2"]
    assert filtered.json() == [{"id": "A2", "name": "Owl"}]


async def test_anam_listing_ignores_model(
    client, auth_user, auth_headers, mocker, db_session
) -> None:
    # Arrange
    from assemblix_api.external.avatar.anam import AnamAvatar

    cred = await _make_credential(db_session, auth_user.project_id)

    async def _fake(api_key):
        return [AnamAvatar(id="a1", name="Cara")]

    mocker.patch("assemblix_api.external.avatar.anam.list_avatars", side_effect=_fake)
    # Act
    resp = await client.get(
        f"/api/avatar/credentials/{cred.id}/avatars",
        params={"model": "cara-4"},
        headers=auth_headers,
    )
    # Assert
    assert resp.json() == [{"id": "a1", "name": "Cara"}]


async def test_avatars_400_for_a_non_avatar_credential(
    client, auth_user, auth_headers, db_session
) -> None:
    cred = await _make_credential(
        db_session, auth_user.project_id, cred_type=CredentialsType.OPENAI_TOKEN, value="sk"
    )
    resp = await client.get(f"/api/avatar/credentials/{cred.id}/avatars", headers=auth_headers)
    assert resp.status_code == 400
