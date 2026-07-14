"""GET /api/api-keys/whoami — resolves the calling sk_ key's project."""

from __future__ import annotations

from typing import Any


async def test_whoami_returns_key_project(client: Any, api_key: Any, auth_user: Any) -> None:
    # Arrange: api_key is an sk_ key scoped to auth_user's default project.

    # Act
    resp = await client.get("/api/api-keys/whoami", headers=api_key.headers)

    # Assert
    assert resp.status_code == 200
    assert resp.json() == {"projectId": str(auth_user.project_id)}
