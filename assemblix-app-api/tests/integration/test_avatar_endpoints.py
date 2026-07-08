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

    mocker.patch("assemblix_api.api.rest.avatar.list_avatars", side_effect=_fake)
    # Act
    resp = await client.get(f"/api/avatar/credentials/{cred.id}/avatars", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert resp.json() == [{"id": "a1", "name": "Cara"}]


async def test_list_credential_voices(client, auth_user, auth_headers, mocker, db_session) -> None:
    """GET /api/avatar/credentials/{id}/voices returns the account's voices."""
    # Arrange
    cred = await _make_credential(db_session, auth_user.project_id)

    async def _fake(api_key):
        assert api_key == "anam-key"
        from assemblix_api.external.avatar.anam import AnamVoice

        return [AnamVoice(id="v1", name="Aurora")]

    mocker.patch("assemblix_api.api.rest.avatar.list_voices", side_effect=_fake)
    # Act
    resp = await client.get(f"/api/avatar/credentials/{cred.id}/voices", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert resp.json() == [{"id": "v1", "name": "Aurora"}]


async def test_mint_workflow_session(client, auth_user, auth_headers, mocker, db_session) -> None:
    """A fully-configured avatar (avatarId + voiceId) mints a token with a full persona."""
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
                "voiceId": "voice-uuid",
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
    # The persona is fully defined (avatar + voice + client-brain), so anam does
    # not fall back to a legacy token.
    assert captured["persona"]["avatarId"] == "avatar-uuid"
    assert captured["persona"]["voiceId"] == "voice-uuid"
    assert captured["persona"]["llmId"] == "CUSTOMER_CLIENT_V1"


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


async def test_mint_session_400_when_avatar_or_voice_missing(
    client, auth_user, auth_headers, db_session
) -> None:
    """An avatar config without a selected avatarId/voiceId → 400 (would be legacy)."""
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
