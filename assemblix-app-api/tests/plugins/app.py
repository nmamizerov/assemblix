"""FastAPI app + HTTP client fixtures (rolled-back ``client`` and committed ``api_client``).

Registered as a plugin from ``tests/conftest.py`` (``pytest_plugins``).
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
import pytest_asyncio

from tests.plugins.database import (
    _async_url,
    _dispose_global_async_engine,
    _truncate_all_tables,
)


@pytest.fixture
def app(db_session: Any) -> Any:
    """A fresh FastAPI app whose ``get_db_session`` yields the test session."""
    from assemblix_api.dependencies import get_db_session
    from assemblix_api.main import create_app

    application = create_app()

    async def _override_session() -> Any:
        yield db_session

    application.dependency_overrides[get_db_session] = _override_session
    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app: Any) -> Any:
    """httpx AsyncClient driving the ASGI app in-process (no network)."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        await _dispose_global_async_engine()


@pytest_asyncio.fixture
async def api_client() -> Any:
    """End-to-end client that exercises the REAL production path.

    Unlike ``client``, it does NOT override ``get_db_session``: each request commits
    to the container DB, so background workflow execution (``run_workflow_isolated``,
    which opens its own session) sees the committed data — exactly like prod.

    The app's global async engine is pinned to a fresh NullPool engine bound to
    this test's event loop (so the background isolated session and the request
    sessions share it without cross-loop asyncpg errors), and all tables are
    truncated afterwards to isolate the next test.
    """
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from assemblix_api.main import create_app

    engine_module = importlib.import_module("assemblix_api.database.engine")
    # Pin a fresh NullPool engine on THIS loop (don't dispose any prior one
    # cross-loop — the `client` fixture disposes its own engine in-loop).
    engine_module.async_engine = create_async_engine(_async_url(), poolclass=NullPool)

    application = create_app()
    transport = ASGITransport(app=application)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        await _truncate_all_tables()
        await _dispose_global_async_engine()
