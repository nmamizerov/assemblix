"""API-key project-scope enforcement across CRUD routers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest_asyncio

from assemblix_api.core.auth_context import AuthContext


@pytest_asyncio.fixture
async def second_project(client, auth_headers) -> str:
    """A second project in the SAME organization as auth_user's default project."""
    resp = await client.post(
        "/api/projects/",
        json={"name": "Second Project"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_resolve_context_returns_user_and_key(db_session: Any, api_key) -> None:
    # Arrange
    from assemblix_api.database.repositories.api_key_repository import APIKeyRepository
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )
    from assemblix_api.database.repositories.project_repository import ProjectRepository
    from assemblix_api.database.repositories.user_repository import UserRepository
    from assemblix_api.services.api_key_service import APIKeyService

    service = APIKeyService(
        APIKeyRepository(db_session),
        UserRepository(db_session),
        ProjectRepository(db_session),
        OrganizationRepository(db_session),
    )

    # Act
    ctx = await service.resolve_context(api_key.plain)

    # Assert
    assert ctx is not None
    user, key = ctx
    assert key.id == api_key.record.id
    assert key.project_id == api_key.record.project_id
    assert user.id is not None


async def test_auth_context_dataclass_holds_scope() -> None:
    # Arrange / Act
    ctx = AuthContext(user=SimpleNamespace(id="u"), scoped_project_id=None)  # type: ignore[arg-type]

    # Assert
    assert ctx.scoped_project_id is None
