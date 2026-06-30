# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Pluggable rate-limit backends. In-memory for single-process self-host, Redis for multi-replica."""

from __future__ import annotations

import time
from typing import Protocol
from uuid import uuid4

import redis.asyncio as aioredis


class RateLimitBackend(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Record one hit. Return True if within `limit` for the rolling window, else False."""
        ...


class InMemoryRateLimitBackend:
    """Process-local sliding window. Correct only for a single process (see Phase 4 plan)."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket = [t for t in self._hits.get(key, []) if t > cutoff]
        if len(bucket) >= limit:
            self._hits[key] = bucket
            return False
        bucket.append(now)
        self._hits[key] = bucket
        return True


class RedisRateLimitBackend:
    """Sliding window via a sorted set scored by timestamp. Atomic per key via pipeline."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        rl_key = f"ratelimit:{key}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(rl_key, 0, cutoff)
            # Each hit gets a unique member (uuid) with score = timestamp. Uniqueness ensures
            # concurrent hits within same time.time() float resolution are counted separately.
            pipe.zadd(rl_key, {f"{now}:{uuid4()}": now})
            pipe.zcard(rl_key)
            pipe.expire(rl_key, window_seconds)
            _, _, count, _ = await pipe.execute()
        return int(count) <= limit
