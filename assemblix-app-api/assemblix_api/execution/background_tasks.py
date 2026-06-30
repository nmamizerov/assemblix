"""Registry of fire-and-forget execution tasks, drained on graceful shutdown.

asyncio keeps only weak references to tasks created with create_task(), so we
hold strong references here both to prevent premature GC and to be able to wait
for in-flight executions when the process receives SIGTERM.
"""

from __future__ import annotations

import asyncio

import structlog

logger = structlog.get_logger(__name__)


class BackgroundTaskRegistry:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def track(self, task: asyncio.Task) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def pending_count(self) -> int:
        return len(self._tasks)

    async def drain(self, timeout: float) -> int:
        """Wait up to `timeout` seconds for tracked tasks to finish.

        Returns the number of tasks still pending after the timeout (0 = all done).
        """
        pending = {t for t in self._tasks if not t.done()}
        if not pending:
            return 0
        logger.info("shutdown.draining_tasks", count=len(pending), timeout=timeout)
        _, still_pending = await asyncio.wait(pending, timeout=timeout)
        if still_pending:
            logger.warning("shutdown.tasks_unfinished", count=len(still_pending))
        return len(still_pending)


# Process-wide singleton.
background_task_registry = BackgroundTaskRegistry()
