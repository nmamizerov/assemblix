"""Health and readiness probes for liveness/readiness checks.

Routes:
- GET /health  — liveness probe. No I/O; always returns 200 while the process is up.
- GET /ready   — readiness probe. Runs SELECT 1 against the DB; optionally pings Redis.
                 Returns 503 if any required dependency is down.
"""

from fastapi import APIRouter, Response

from assemblix_api.core.settings import get_settings
from assemblix_api.database.engine import check_async_db_connection

router = APIRouter(tags=["health"])


@router.get("/health", include_in_schema=True)
async def health() -> dict:
    """Liveness probe — no I/O. Returns 200 as long as the process is running."""
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}


@router.get("/ready", include_in_schema=True)
async def ready(response: Response) -> dict:
    """Readiness probe — checks DB connectivity and optionally Redis.

    Returns 200 when all required dependencies are reachable, 503 otherwise.
    Each dependency is checked independently so a single failure does not mask others.
    """
    from assemblix_api.core.redis_client import get_redis, is_redis_enabled

    out: dict[str, str] = {"db": "ok", "redis": "skipped"}

    # --- DB check ---
    db_ok = await check_async_db_connection()
    if not db_ok:
        out["db"] = "down"
        response.status_code = 503

    # --- Redis check (optional) ---
    if is_redis_enabled():
        try:
            client = await get_redis()
            await client.ping()
            out["redis"] = "ok"
        except Exception:
            out["redis"] = "down"
            response.status_code = 503

    return out
