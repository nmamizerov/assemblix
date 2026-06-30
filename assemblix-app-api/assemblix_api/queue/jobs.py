"""Arq job handlers for the execution queue."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.engine import get_async_engine

# Module-level imports so tests can patch them as assemblix_api.queue.jobs.*
from assemblix_api.database.repositories.workflow_repository import WorkflowRepository
from assemblix_api.dependencies import build_executor

logger = structlog.get_logger(__name__)


async def _signal_completion(ctx: dict, execution_id: UUID) -> None:
    """Publish the completion signal for a queued execution (best-effort)."""
    try:
        from assemblix_api.queue.completion import publish_completion

        redis = ctx.get("redis")
        if redis is not None:
            await publish_completion(redis, execution_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "queue.job.completion_signal_failed",
            execution_id=str(execution_id),
            exc_info=True,
        )


async def run_workflow_job(
    ctx: dict,
    execution_id: str,
    workflow_id: str,
    input_data: dict,
    token_id: str | None,
    chat_session_id: str | None,
) -> None:
    """
    Arq job: run a single workflow execution.

    Opens its own AsyncSession, builds all services via build_executor, loads the
    workflow, and calls executor.execute().  Commits on success; rolls back and logs
    on any exception so the job is marked as failed by Arq.

    Args:
        ctx: Arq worker context (not used directly but required by the Arq protocol).
        execution_id: UUID string of the pre-created QUEUED execution row.
        workflow_id: UUID string of the workflow to execute.
        input_data: Input data dict passed to the executor.
        token_id: UUID string of the API key, or None for debug mode.
        chat_session_id: UUID string of the chat session, or None.
    """
    exec_uuid = UUID(execution_id)
    wf_uuid = UUID(workflow_id)
    token_uuid = UUID(token_id) if token_id else None
    chat_uuid = UUID(chat_session_id) if chat_session_id else None

    engine = get_async_engine()

    # expire_on_commit=False: the executor commits at node boundaries (to release the
    # DB connection during LLM/HTTP awaits), and the long-lived `execution` ORM object
    # must stay usable across those commits without a lazy reload (MissingGreenlet).
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            workflow_repo = WorkflowRepository(session)
            workflow = await workflow_repo.get_by_id(wf_uuid)
            if workflow is None:
                logger.warning(
                    "queue.job.workflow_not_found",
                    execution_id=execution_id,
                    workflow_id=workflow_id,
                )
                return

            executor = await build_executor(session)

            await executor.execute(
                workflow=workflow,
                input_data=input_data,
                token_id=token_uuid,
                chat_session_id=chat_uuid,
                execution_id=exec_uuid,
            )

            await session.commit()

        except Exception:
            await session.rollback()
            logger.exception(
                "queue.job.execution_failed",
                execution_id=execution_id,
                workflow_id=workflow_id,
            )
            raise
        finally:
            # Wake any synchronous /execute caller waiting on this execution.
            # Best-effort and after commit, so the waiter reads the terminal
            # status; a Redis hiccup here must never fail the job.
            await _signal_completion(ctx, exec_uuid)
