"""Smoke checks for the DB-backed harness (container, isolation, auth, client).

These prove the scaffolding works end to end; real coverage-zone test cases are
written on top of the same fixtures.
"""

from __future__ import annotations

from sqlalchemy import func, select

from assemblix_api.database.models.user import User


async def test_database_container_is_fresh(db_session) -> None:
    """The throwaway container starts empty (migrations applied, no rows)."""
    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 0


async def test_user_factory_persists_in_session(user_factory) -> None:
    """The user factory creates a user with a personal org + default project."""
    created = await user_factory()
    assert created.user.id is not None
    assert created.organization_id is not None
    assert created.project_id is not None
    assert created.token  # JWT issued


async def test_rollback_isolation_between_tests(db_session) -> None:
    """The user created in the previous test must not leak into this one.

    Confirms the per-test transaction rollback gives a clean slate every time.
    """
    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 0


async def test_health_and_ready_endpoints(client) -> None:
    """Liveness always 200; readiness 200 because the container DB is reachable."""
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200


async def test_jwt_auth_path_through_client(client, auth_headers) -> None:
    """A JWT issued by the factory authenticates against a protected endpoint."""
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200


async def test_api_key_auth_path_through_client(client, api_key) -> None:
    """An ``sk_`` API key authenticates against the same protected endpoint."""
    assert api_key.plain.startswith("sk_")
    resp = await client.get("/api/auth/me", headers=api_key.headers)
    assert resp.status_code == 200


async def test_unauthenticated_request_is_rejected(client) -> None:
    """No credentials → 401/403, proving the auth dependency is wired."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)
