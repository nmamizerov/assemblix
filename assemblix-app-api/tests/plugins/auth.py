"""Authentication fixtures: JWT user factory + ``sk_`` API key.

Registered as a plugin from ``tests/conftest.py`` (``pytest_plugins``).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def user_factory(db_session: Any) -> Any:
    """Factory creating real users (with personal org + default project + JWT).

    Reuses ``UserService`` so the bootstrap matches production exactly. Returns a
    ``SimpleNamespace(user, token, organization_id, project_id, password)``.
    """
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )
    from assemblix_api.database.repositories.organization_user_repository import (
        OrganizationUserRepository,
    )
    from assemblix_api.database.repositories.project_repository import ProjectRepository
    from assemblix_api.database.repositories.user_repository import UserRepository
    from assemblix_api.services.user_service import UserService

    service = UserService(
        UserRepository(db_session),
        OrganizationRepository(db_session),
        OrganizationUserRepository(db_session),
        ProjectRepository(db_session),
    )

    async def _make(email: str | None = None, password: str = "testpass123") -> SimpleNamespace:
        # Use a non-reserved domain — pydantic's email validator rejects .local.
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        user, token, org_id, project_id = await service.register_and_login(
            email=email, password=password
        )
        return SimpleNamespace(
            user=user,
            token=token,
            organization_id=org_id,
            project_id=project_id,
            password=password,
        )

    return _make


@pytest_asyncio.fixture
async def auth_user(user_factory: Any) -> SimpleNamespace:
    """A single ready-to-use authenticated user."""
    return await user_factory()


@pytest.fixture
def auth_headers(auth_user: SimpleNamespace) -> dict[str, str]:
    """Bearer headers for the JWT path."""
    return {"Authorization": f"Bearer {auth_user.token}"}


@pytest_asyncio.fixture
async def api_key(db_session: Any, auth_user: SimpleNamespace) -> SimpleNamespace:
    """Create an ``sk_`` API key for the user's default project.

    Returns ``SimpleNamespace(record, plain, headers)`` — ``plain`` is the raw key
    (only available at creation), ``headers`` are ready Bearer headers.
    """
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
    record, plain = await service.create_api_key(project_id=auth_user.project_id, name="test-key")
    return SimpleNamespace(record=record, plain=plain, headers={"Authorization": f"Bearer {plain}"})
