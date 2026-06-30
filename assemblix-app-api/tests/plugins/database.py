"""Database fixtures: app runtime, transactional session, committed-DB engine.

Registered as a plugin from ``tests/conftest.py`` (``pytest_plugins``).
"""

from __future__ import annotations

import importlib
import os
from typing import Any

import pytest
import pytest_asyncio


def _async_url() -> str:
    """asyncpg URL for the container DB (from the env set in pytest_configure)."""
    return os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")


async def _dispose_global_async_engine() -> None:
    """Dispose the app's global async engine (must run in its own event loop).

    Endpoints like /ready call get_async_engine() directly (not via the overridden
    dependency), creating a pooled global engine bound to the current test loop.
    Disposing it here — in the same loop — stops a stale, dead-loop connection from
    leaking into a later test (which would raise asyncpg "attached to a different
    loop").
    """
    # importlib (not `import ... as`) because assemblix_api.database re-exports a
    # name `engine` (the sync Engine), shadowing the submodule attribute.
    engine_module = importlib.import_module("assemblix_api.database.engine")

    if engine_module.async_engine is not None:
        await engine_module.async_engine.dispose()
        engine_module.async_engine = None


async def _truncate_all_tables() -> None:
    """Wipe every table on the container DB (used to isolate e2e / committed tests)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from assemblix_api.database.models import Base

    engine = create_async_engine(_async_url(), poolclass=NullPool)
    # Order is irrelevant for TRUNCATE ... CASCADE, so use the raw table set (avoids
    # the sorted_tables cycle warning from mutually-dependent FKs like users<->orgs).
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.tables.values())
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _app_runtime() -> Any:
    """Initialise process-wide runtime the app normally sets up in its lifespan.

    Encryption service + node registry are global singletons; do it once so both
    service-level tests and HTTP/client tests have a ready runtime without
    spinning the FastAPI lifespan.
    """
    from assemblix_api.core.encryption import init_encryption_service
    from assemblix_api.core.node_loader import load_builtin_nodes
    from assemblix_api.core.settings import get_settings

    settings = get_settings()
    init_encryption_service(settings.encryption_key)
    load_builtin_nodes()
    yield


@pytest_asyncio.fixture
async def db_engine() -> Any:
    """A function-scoped async engine bound to the container.

    Function scope + NullPool keeps each test on its own event loop without
    asyncpg "attached to a different loop" errors.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(_async_url(), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: Any) -> Any:
    """Per-test session inside an outer transaction that is always rolled back.

    ``join_transaction_mode="create_savepoint"`` turns any ``commit()`` a
    service/endpoint performs into a savepoint release, so data is visible within
    the test (and to the app over the same connection) yet discarded at teardown.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    conn = await db_engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def committed_db() -> Any:
    """Pin a fresh NullPool engine on this loop; truncate all tables afterwards.

    For tests that need data **committed** to the container DB so a separate session
    sees it (e.g. the Arq worker / queue tests), instead of the rolled-back
    ``db_session``. Yields the engine; ``get_async_engine()`` returns the same one,
    so worker jobs share it without cross-loop asyncpg errors.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine_module = importlib.import_module("assemblix_api.database.engine")
    engine_module.async_engine = create_async_engine(_async_url(), poolclass=NullPool)
    try:
        yield engine_module.async_engine
    finally:
        await _truncate_all_tables()
        await _dispose_global_async_engine()
