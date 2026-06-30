"""
Distributed concurrency limiter — best-effort Redis-backed semaphores.

Caps how many agent (LLM) calls run at once per organization and per LLM provider, so
one tenant can't starve the worker pool and a burst can't blow a provider's rate limit.
This is the cross-worker counterpart to per-worker WORKER_MAX_JOBS (n8n/Inngest call
this per-key concurrency).

Design notes:
- Best-effort: when no slot frees within the acquire timeout we proceed anyway and log a
  warning. The limiter smooths bursts and protects providers; it never fails a workflow.
- No-op when Redis is not configured or the limit is <= 0 — so the single-process
  self-host default is unaffected.
- Each in-flight call is one member of a Redis sorted set, scored by an expiry deadline
  computed from the Redis server clock (so scores are comparable across workers — a
  per-process monotonic clock is not). Acquire is a single atomic Lua script that purges
  expired holders, checks the count, and adds the new holder, so concurrent workers can't
  over-admit. A slot leaked by a crashed worker self-heals once its expiry passes,
  regardless of how busy the key is — the bug an INCR/DECR counter with a shared TTL had.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

import structlog

logger = structlog.get_logger(__name__)

# Atomic acquire. Uses the Redis server clock (TIME) so holder-expiry scores are
# comparable across workers. Purges expired holders, then admits this one if under limit.
#   KEYS[1] = semaphore key
#   ARGV[1] = limit, ARGV[2] = holder token, ARGV[3] = slot lifetime (ms)
# Returns 1 when the slot was acquired, 0 otherwise.
_ACQUIRE_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[1]) then
    redis.call('ZADD', KEYS[1], now + tonumber(ARGV[3]), ARGV[2])
    redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[3]) + 1000)
    return 1
end
return 0
"""


async def _try_acquire(redis, key: str, limit: int, token: str, hold_ms: int) -> bool:
    """Atomically take a slot if under the limit. Returns True when acquired."""
    result = await redis.eval(_ACQUIRE_LUA, 1, key, limit, token, hold_ms)
    return bool(result)


@asynccontextmanager
async def concurrency_slot(
    redis, key: str, limit: int, *, acquire_timeout: float, hold_timeout: float
):
    """Hold one slot of the semaphore at `key` for the duration of the block.

    No-op when redis is None or limit <= 0. Polls for a free slot up to acquire_timeout,
    then proceeds regardless (best-effort backpressure).

    `hold_timeout` is the longest the wrapped call can run; the slot's expiry is sized off
    it (plus the acquire wait) so a crashed worker's slot self-heals only after the call
    could no longer be in flight — never mid-call.
    """
    if redis is None or limit <= 0:
        yield
        return

    token = uuid.uuid4().hex
    # A holder's slot becomes reclaimable only once it has been held longer than the call
    # could possibly run (hold_timeout) plus the acquire wait — generous on purpose; it
    # only bounds how long a *crashed* worker's slot lingers, never expires a live call.
    hold_ms = int((hold_timeout + acquire_timeout) * 1000) + 1000
    acquired = False
    loop = asyncio.get_event_loop()
    deadline = loop.time() + acquire_timeout
    delay = 0.05
    while True:
        try:
            if await _try_acquire(redis, key, limit, token, hold_ms):
                acquired = True
                break
        except Exception:
            # Redis hiccup: fail open (proceed) rather than block the workflow.
            logger.warning("concurrency.slot.acquire_failed", key=key)
            break
        if loop.time() >= deadline:
            logger.warning("concurrency.slot.timeout_proceeding", key=key, limit=limit)
            break
        await asyncio.sleep(min(delay, 0.5))
        delay *= 1.5

    try:
        yield
    finally:
        if acquired:
            try:
                await redis.zrem(key, token)
            except Exception:
                logger.warning("concurrency.slot.release_failed", key=key)


@asynccontextmanager
async def agent_call_guard(organization_id, provider: str, *, hold_timeout: float):
    """Wrap an agent LLM call with the org + provider concurrency caps.

    Resolves Redis and the configured limits lazily; a no-op when Redis is unset or both
    limits are 0. Nesting two slots means the call runs only when BOTH caps allow it.
    `hold_timeout` is the call's own wall-clock budget — it sizes the slot's leak TTL.
    """
    from assemblix_api.core.redis_client import get_redis, is_redis_enabled
    from assemblix_api.core.settings import get_settings

    settings = get_settings()
    redis = await get_redis() if is_redis_enabled() else None
    timeout = settings.concurrency_acquire_timeout_seconds

    org_key = f"concurrency:org:{organization_id}" if organization_id else "concurrency:org:none"
    provider_key = f"concurrency:provider:{provider}"

    async with (
        concurrency_slot(
            redis,
            org_key,
            settings.org_max_concurrency,
            acquire_timeout=timeout,
            hold_timeout=hold_timeout,
        ),
        concurrency_slot(
            redis,
            provider_key,
            settings.provider_max_concurrency,
            acquire_timeout=timeout,
            hold_timeout=hold_timeout,
        ),
    ):
        yield
