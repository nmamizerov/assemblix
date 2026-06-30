"""Fixtures for queue (Arq) tests — run the app with Redis-specific settings.

These tests simulate the production queue path: a Redis container, the API
configured with ``EXECUTION_QUEUE_ENABLED=true`` + ``REDIS_URL``, and workflows
launched via real API requests that get enqueued and processed by an Arq worker.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

import pytest
import pytest_asyncio


@pytest.fixture(scope="module")
def redis_url() -> Any:
    """A throwaway Redis container for the Arq queue (sync, module-scoped)."""
    from testcontainers.redis import RedisContainer

    container = RedisContainer("redis:7-alpine")
    container.start()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    try:
        yield f"redis://{host}:{port}"
    finally:
        container.stop()


@pytest_asyncio.fixture
async def queue_runtime(redis_url, committed_db) -> Any:
    """Flip the app into queue mode (Redis on) for one test, then restore.

    Builds on ``committed_db`` (pins a NullPool engine + truncates afterwards) and
    additionally: sets the queue/Redis env, clears the settings cache, and resets
    the cached Redis/Arq/rate-limit globals so the request path and the worker use
    THIS test's Redis. Everything is reverted on teardown so other tests stay on the
    default no-Redis profile.
    """
    import assemblix_api.api.rest.auth as auth_mod
    import assemblix_api.core.redis_client as redis_client
    import assemblix_api.dependencies as deps
    from assemblix_api.core.settings import get_settings

    os.environ["EXECUTION_QUEUE_ENABLED"] = "true"
    os.environ["REDIS_URL"] = redis_url
    get_settings.cache_clear()
    deps._arq_pool = None
    deps._rate_limit_service = None  # rebuilt Redis-backed for this test
    redis_client._client = None
    auth_mod._rate_limit_backend = None

    try:
        yield
    finally:
        # Restore the default (no-Redis) profile FIRST so a failing pool close
        # can't leave other tests pointed at this (soon-stopped) Redis.
        os.environ["EXECUTION_QUEUE_ENABLED"] = "false"
        os.environ["REDIS_URL"] = ""
        get_settings.cache_clear()
        with contextlib.suppress(Exception):
            await deps.close_arq_pool()
        with contextlib.suppress(Exception):
            await redis_client.close_redis()
        deps._arq_pool = None
        deps._rate_limit_service = None  # next tests rebuild it in-memory
        redis_client._client = None
        auth_mod._rate_limit_backend = None


@pytest_asyncio.fixture
async def queue_client(queue_runtime) -> Any:
    """Real ASGI client (commits to the DB) with the queue profile active."""
    from httpx import ASGITransport, AsyncClient

    from assemblix_api.main import create_app

    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
