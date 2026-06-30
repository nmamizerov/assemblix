"""
Arq WorkerSettings for the execution queue.

Run with:
    uv run arq assemblix_api.queue.worker.WorkerSettings

Redis is required at runtime but NOT at import time — importing this module is
safe even when REDIS_URL is unset (e.g. during test collection).
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.core.settings import get_settings
from assemblix_api.database.engine import get_async_engine
from assemblix_api.database.repositories.execution_repository import ExecutionRepository
from assemblix_api.queue.jobs import run_workflow_job

logger = structlog.get_logger(__name__)


async def startup(ctx: dict) -> None:
    """
    Worker startup hook — initialise singletons and re-enqueue orphaned executions.

    Called once per worker process before any job runs. After setting up the node
    registry and encryption service, runs an orphan-recovery scan: any execution
    stuck in QUEUED or RUNNING for longer than 2× graceful_shutdown_timeout_seconds
    is considered orphaned (the worker that owned it crashed or was redeployed) and
    is re-enqueued so it resumes from its last checkpoint.

    Re-enqueueing uses _job_id=str(execution.id), which makes the operation
    idempotent — Arq will not create a duplicate job if one is already queued under
    that id.

    The scan is best-effort: any exception is logged and swallowed so that a
    transient DB error never prevents a worker from starting.
    """
    from assemblix_api.core.encryption import init_encryption_service
    from assemblix_api.core.node_loader import load_builtin_nodes, load_plugin_nodes
    from assemblix_api.core.node_registry import NodeRegistry
    from assemblix_api.core.settings import validate_security_config

    settings = get_settings()
    validate_security_config(settings)
    init_encryption_service(settings.encryption_key)
    load_builtin_nodes()
    load_plugin_nodes()
    # Instantiate the singleton so it is warm for the first job.
    NodeRegistry()

    # --- Orphan recovery scan ---
    # Use 2× graceful_shutdown_timeout as the staleness cutoff.  A row younger
    # than one graceful-shutdown window may still be legitimately running on
    # another live worker, so we leave it alone.
    cutoff_seconds = settings.graceful_shutdown_timeout_seconds * 2
    try:
        async with AsyncSession(get_async_engine()) as session:
            repo = ExecutionRepository(session)
            orphans = await repo.find_resumable(older_than_seconds=cutoff_seconds)

        logger.info(
            "queue.worker.orphan_scan",
            count=len(orphans),
            cutoff_seconds=cutoff_seconds,
        )

        for orphan in orphans:
            input_data: dict = (orphan.meta_data or {}).get("input_data", {})
            token_id_str = str(orphan.token_id) if orphan.token_id is not None else None
            chat_session_id_str = (
                str(orphan.chat_session_id) if orphan.chat_session_id is not None else None
            )
            await ctx["redis"].enqueue_job(
                "run_workflow_job",
                str(orphan.id),
                str(orphan.workflow_id),
                input_data,
                token_id_str,
                chat_session_id_str,
                _job_id=str(orphan.id),
            )
            logger.info(
                "queue.worker.orphan_requeued",
                execution_id=str(orphan.id),
            )
    except Exception:
        # Recovery is best-effort — a DB error must not prevent the worker from starting.
        logger.exception("queue.worker.orphan_scan_failed")

    # --- Prometheus metrics scrape port (best-effort) ---
    # Start a standalone HTTP server so Prometheus can scrape the worker tier
    # independently from the API process.  If the port is already taken (e.g. two
    # workers on the same host) we log a warning and continue — worker startup must
    # not fail because of a metrics port conflict.
    if settings.metrics_enabled and settings.worker_metrics_enabled:
        try:
            from prometheus_client import start_http_server

            start_http_server(settings.metrics_port)
            logger.info("queue.worker.metrics_server_started", port=settings.metrics_port)
        except OSError:
            logger.warning(
                "queue.worker.metrics_port_in_use",
                port=settings.metrics_port,
                reason="port already bound — metrics server not started",
            )
        except Exception:
            logger.warning("queue.worker.metrics_server_failed")

    logger.info("queue.worker.startup_complete")


async def shutdown(ctx: dict) -> None:
    """
    Worker shutdown hook — close shared resources gracefully.

    Called once per worker process after all in-flight jobs finish.
    """
    from assemblix_api.core.redis_client import close_redis

    await close_redis()
    logger.info("queue.worker.shutdown_complete")


def _build_redis_settings():  # type: ignore[return]
    """
    Return arq RedisSettings built from REDIS_URL, or None if unset.

    Importing at module level would raise if arq is not installed or REDIS_URL
    is unset during test collection, so we defer to a helper.
    """
    settings = get_settings()
    if not settings.redis_url:
        # Returning None here causes Arq to use its default (localhost:6379).
        # The worker will fail to connect at runtime, which is the correct
        # behaviour when REDIS_URL is not configured.
        return None

    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(settings.redis_url)


def _worker_max_jobs() -> int:
    """Concurrent jobs per worker process (env WORKER_MAX_JOBS, default 10)."""
    return get_settings().worker_max_jobs


def _worker_job_timeout() -> int:
    """
    Per-job timeout for Arq, in seconds.

    Arq's default (300s) is shorter than the workflow wall-clock ceiling
    (WORKFLOW_EXECUTION_TIMEOUT_SECONDS, default 1800s), which would let Arq kill a
    long-but-valid workflow mid-run. Align them with a small buffer so the executor's
    own timeout fires first.
    """
    return get_settings().workflow_execution_timeout_seconds + 60


class WorkerSettings:
    """Arq worker configuration for the Assemblix execution queue."""

    functions = [run_workflow_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _build_redis_settings()
    # Concurrency and per-job timeout are env-tunable (no image rebuild needed).
    max_jobs = _worker_max_jobs()
    job_timeout = _worker_job_timeout()
