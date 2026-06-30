"""Redis Pub/Sub transport for debug events, so SSE works across replicas."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID

import redis.asyncio as aioredis

_TERMINAL = {"execution_complete", "error"}


class RedisDebugEventTransport:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    @staticmethod
    def _channel(execution_id: UUID) -> str:
        return f"debug:{execution_id}"

    async def publish(self, execution_id: UUID, payload: dict) -> None:
        await self._redis.publish(self._channel(execution_id), json.dumps(payload, default=str))

    async def subscribe(self, execution_id: UUID) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel(execution_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    # Skip a malformed message instead of terminating the stream.
                    continue
                yield payload
                if payload.get("event_type") in _TERMINAL:
                    break
        finally:
            await pubsub.unsubscribe(self._channel(execution_id))
            await pubsub.aclose()
