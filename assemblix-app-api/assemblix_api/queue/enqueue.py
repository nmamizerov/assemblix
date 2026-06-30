"""Helper to atomically create a QUEUED execution row and push an Arq job."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from arq.connections import ArqRedis

    from assemblix_api.services.execution_service import ExecutionService

logger = logging.getLogger(__name__)

# Arq stores queued jobs in a sorted set under this key (internal detail,
# stable across Arq 0.25+). We read it only for the queue-depth gauge — if the
# key or API changes, the gauge simply falls back to a no-op increment.
_ARQ_QUEUE_KEY = b"arq:queue"


async def _update_queue_depth(arq_redis: ArqRedis) -> None:
    """Best-effort update of the assemblix_queue_depth Prometheus gauge.

    Reads the Arq sorted-set length (pending jobs) and sets the gauge.  Any
    failure is swallowed with a warning so it never disrupts enqueue callers.
    This is a monitoring convenience — losing this update is acceptable.
    """
    try:
        from assemblix_api.core.metrics import set_queue_depth

        # arq.ArqRedis inherits from redis.asyncio.Redis; zcard is available.
        depth = await arq_redis.zcard(_ARQ_QUEUE_KEY)
        set_queue_depth(int(depth))
    except Exception:  # noqa: BLE001
        logger.warning("queue_depth_gauge_update_failed", exc_info=True)


async def enqueue_execution(
    execution_service: ExecutionService,
    arq_redis: ArqRedis,
    *,
    workflow_id: UUID,
    input_data: dict,
    token_id: UUID | None,
    chat_session_id: UUID | None,
) -> UUID:
    """
    Create a QUEUED execution row and push run_workflow_job to the Arq queue.

    The Arq job uses _job_id=str(execution_id) so that re-enqueuing the same
    execution is idempotent (Arq deduplicates by job_id).

    After enqueuing, updates the assemblix_queue_depth gauge best-effort (any
    Redis error is swallowed so the caller is never affected).

    Args:
        execution_service: An ExecutionService instance with create_queued().
        arq_redis: An arq.ArqRedis connection pool (from arq.create_pool).
        workflow_id: ID of the workflow to execute.
        input_data: Input data forwarded to the executor.
        token_id: API key ID, or None for debug mode.
        chat_session_id: Chat session ID, or None.

    Returns:
        The UUID of the newly created execution row.
    """
    row = await execution_service.create_queued(
        workflow_id=workflow_id,
        token_id=token_id,
        initial_state={},
        input_data=input_data,
        chat_session_id=chat_session_id,
    )

    await arq_redis.enqueue_job(
        "run_workflow_job",
        str(row.id),
        str(workflow_id),
        input_data,
        str(token_id) if token_id is not None else None,
        str(chat_session_id) if chat_session_id is not None else None,
        _job_id=str(row.id),
    )

    # Update queue-depth gauge after enqueuing (best-effort, never raises).
    await _update_queue_depth(arq_redis)

    return row.id
