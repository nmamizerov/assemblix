"""
Background helper for dispatching execution-failure notifications.

Opens its own DB session, so it is safe to call from `asyncio.create_task(...)`
after the main execution session is closed. Accepts only primitives, never ORM
objects bound to another session.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.repositories.notification_channel_repository import (
    NotificationChannelRepository,
)

from .dispatcher import ExecutionFailurePayload, NotificationDispatcher

logger = structlog.get_logger(__name__)


async def dispatch_execution_failure(
    *,
    project_id: UUID,
    execution_id: UUID,
    workflow_name: str,
    error_type: str | None = None,
    error_message: str | None = None,
    failed_node_id: str | None = None,
) -> None:
    """
    Dispatch an execution-failure notification to the project channels.

    Any error is logged and suppressed so the background task does not crash the
    event loop.
    """
    from assemblix_api.database.engine import get_async_engine

    try:
        engine = get_async_engine()
        async with AsyncSession(engine) as session:
            repository = NotificationChannelRepository(session)
            dispatcher = NotificationDispatcher(repository)
            await dispatcher.notify_execution_failure(
                ExecutionFailurePayload(
                    project_id=project_id,
                    execution_id=execution_id,
                    workflow_name=workflow_name,
                    error_type=error_type,
                    error_message=error_message,
                    failed_node_id=failed_node_id,
                )
            )
    except Exception:
        logger.exception(
            "notification.dispatch_failed",
            project_id=str(project_id),
            execution_id=str(execution_id),
        )
