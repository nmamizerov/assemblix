"""Redis Pub/Sub completion signal for queued executions.

Lets the synchronous /execute endpoint await a job that runs on a separate Arq
worker: the worker publishes a one-shot "done" message when the execution
reaches a terminal state, and the endpoint wakes up immediately instead of
polling.  Pub/Sub is global across the Redis instance (db-independent), so the
worker pool connection and the API client connection interoperate even when
they target different logical databases.

The endpoint must subscribe *before* it reads the terminal status from the DB,
so it never misses a completion that lands between the read and the wait:

    pubsub = await open_completion_subscription(redis, execution_id)
    try:
        result = <read DB>            # catches a worker that already finished
        if not terminal:
            await wait_for_signal(pubsub, timeout)
            result = <read DB again>  # signalled — now terminal
    finally:
        await close_completion_subscription(pubsub, execution_id)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from redis.asyncio.client import PubSub

_CHANNEL_PREFIX = "execution:done:"


def completion_channel(execution_id: UUID) -> str:
    return f"{_CHANNEL_PREFIX}{execution_id}"


async def publish_completion(redis: aioredis.Redis, execution_id: UUID) -> None:
    """Publish a one-shot completion signal for a queued execution.

    Called by the worker after the execution row is committed in a terminal
    state.  Best-effort: a waiter that subscribed earlier wakes immediately; if
    none is listening the message is simply dropped.
    """
    await redis.publish(completion_channel(execution_id), "done")


async def open_completion_subscription(redis: aioredis.Redis, execution_id: UUID) -> PubSub:
    """Subscribe to an execution's completion channel and return the PubSub handle."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(completion_channel(execution_id))
    return pubsub


async def close_completion_subscription(pubsub: PubSub, execution_id: UUID) -> None:
    """Unsubscribe and release the PubSub connection."""
    await pubsub.unsubscribe(completion_channel(execution_id))
    await pubsub.aclose()


async def wait_for_signal(pubsub: PubSub, timeout: float) -> bool:
    """Block on an already-subscribed PubSub until a publish arrives or timeout.

    Returns True if the completion signal arrived, False on timeout.  Subscribe
    acknowledgements are skipped; only a real "message" counts.
    """
    try:
        await asyncio.wait_for(_next_message(pubsub), timeout=timeout)
        return True
    except TimeoutError:
        return False


async def _next_message(pubsub: PubSub) -> None:
    async for message in pubsub.listen():
        if message.get("type") == "message":
            return
