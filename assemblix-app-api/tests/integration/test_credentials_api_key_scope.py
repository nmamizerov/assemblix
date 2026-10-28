"""Credential listing with a project API key (used by the MCP server's list_credentials):
project_id is implicit and secret values are never returned."""

from __future__ import annotations

from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.repositories.credentials_repository import CredentialsRepository


async def test_list_credentials_defaults_to_key_project(
    client, api_key, db_session, auth_user
) -> None:
    # Arrange
    cred = await CredentialsRepository(db_session).create(
        project_id=auth_user.project_id,
        type=CredentialsType.TYPESAFE_TOKEN,
        name="jev",
        value="ts-secret",
    )
    await db_session.commit()
    # Act
    resp = await client.get(
        "/api/credentials/", params={"type": "typesafe_token"}, headers=api_key.headers
    )
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert [c["id"] for c in body] == [str(cred.id)]
    assert "value" not in body[0]
    assert "ts-secret" not in resp.text


async def test_list_credentials_jwt_without_project_id_returns_400(client, auth_headers) -> None:
    # Act
    resp = await client.get("/api/credentials/", headers=auth_headers)
    # Assert
    assert resp.status_code == 400
