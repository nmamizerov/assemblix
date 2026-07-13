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


async def test_get_auth_context_api_key_sets_scope(db_session: Any, api_key) -> None:
    # Arrange
    from fastapi.security import HTTPAuthorizationCredentials

    from assemblix_api.database.repositories.api_key_repository import APIKeyRepository
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )
    from assemblix_api.database.repositories.project_repository import ProjectRepository
    from assemblix_api.database.repositories.user_repository import UserRepository
    from assemblix_api.dependencies import get_auth_context
    from assemblix_api.services.api_key_service import APIKeyService
    from assemblix_api.services.user_service import UserService

    api_key_service = APIKeyService(
        APIKeyRepository(db_session),
        UserRepository(db_session),
        ProjectRepository(db_session),
        OrganizationRepository(db_session),
    )
    user_service = UserService(
        UserRepository(db_session),
        OrganizationRepository(db_session),
        __import__(
            "assemblix_api.database.repositories.organization_user_repository",
            fromlist=["OrganizationUserRepository"],
        ).OrganizationUserRepository(db_session),
        ProjectRepository(db_session),
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=api_key.plain)

    # Act
    ctx = await get_auth_context(
        credentials=creds, user_service=user_service, api_key_service=api_key_service
    )

    # Assert
    assert ctx.scoped_project_id == api_key.record.project_id
