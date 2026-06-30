"""Lazy async Redis client. Redis is optional; callers must check is_redis_enabled() first."""

from __future__ import annotations

import redis.asyncio as aioredis

from assemblix_api.core.settings import get_settings

_client: aioredis.Redis | None = None


def is_redis_enabled() -> bool:
    return bool(get_settings().redis_url)


async def get_redis() -> aioredis.Redis:
    """Return a process-wide Redis client. Raises if REDIS_URL is not configured."""
    global _client
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("Redis is not configured (REDIS_URL is unset)")
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
