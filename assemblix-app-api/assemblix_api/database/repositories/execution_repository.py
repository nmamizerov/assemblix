"""Execution repository - DB operations for executions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Select, and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from assemblix_api.database.models.execution import Execution
from assemblix_api.database.repositories.base_repository import BaseRepository
from assemblix_api.enums import ExecutionStatus

if TYPE_CHECKING:
    from assemblix_api.dto.requests.execution import ExecutionFilters


class ExecutionRepository(BaseRepository[Execution]):
    """Repository for the executions table."""

    def __init__(self, session: AsyncSession):
        super().__init__(Execution, session)

    async def get_by_workflow_id(
        self,
        workflow_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ExecutionStatus | None = None,
    ) -> Sequence[Execution]:
        """Get executions for a workflow, newest first."""
        stmt = select(self._model).where(self._model.workflow_id == workflow_id)

        if status is not None:
            stmt = stmt.where(self._model.status == status)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_project_id_simple(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ExecutionStatus | None = None,
    ) -> Sequence[Execution]:
        """Get executions for a project via join with workflow, newest first."""
        from assemblix_api.database.models.workflow import Workflow

        stmt = (
            select(self._model)
            .join(Workflow, self._model.workflow_id == Workflow.id)
            .where(Workflow.project_id == project_id)
        )

        if status is not None:
            stmt = stmt.where(self._model.status == status)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_chat_session_id(
        self,
        chat_session_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Execution]:
        """Get executions for a chat session, newest first."""
        stmt = (
            select(self._model)
            .where(self._model.chat_session_id == chat_session_id)
            .order_by(self._model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_with_details(self, execution_id: UUID) -> Execution | None:
        """Get an execution with relationships eagerly loaded (steps, workflow, chat_session)."""
        from assemblix_api.database.models.chat_session import ChatSession

        stmt = (
            select(self._model)
            .where(self._model.id == execution_id)
            .options(
                selectinload(self._model.steps),
                selectinload(self._model.workflow),
                selectinload(self._model.chat_session).selectinload(ChatSession.workflow),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _build_filters(self, query: Select[Any], filters: ExecutionFilters) -> Select[Any]:
        """Apply ExecutionFilters to the query."""
        # include_debug: False = non-debug only, True = all (including debug)
        if not filters.include_debug:
            query = query.where(self._model.is_debug == False)

        if filters.workflow_id is not None:
            query = query.where(self._model.workflow_id == filters.workflow_id)

        if filters.chat_session_id is not None:
            query = query.where(self._model.chat_session_id == filters.chat_session_id)

        if filters.client_session_id is not None:
            query = query.where(self._model.client_session_id == filters.client_session_id)

        if filters.status is not None:
            query = query.where(self._model.status == filters.status)

        if filters.date_from is not None:
            query = query.where(self._model.started_at >= filters.date_from)
        if filters.date_to is not None:
            query = query.where(self._model.started_at <= filters.date_to)

        return query

    async def get_executions_list(
        self,
        project_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
        filters: ExecutionFilters | None = None,
    ) -> tuple[Sequence[Execution], int]:
        """Get a filtered, paginated list of project executions plus the total count.

        Returns a tuple of (executions, total). The total is computed before
        limit/offset are applied.
        """
        from assemblix_api.database.models.workflow import Workflow
        from assemblix_api.dto.requests.execution import ExecutionFilters

        if filters is None:
            filters = ExecutionFilters()

        stmt = (
            select(self._model)
            .join(Workflow, self._model.workflow_id == Workflow.id)
            .where(Workflow.project_id == project_id)
        )

        stmt = self._build_filters(stmt, filters)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        from assemblix_api.database.models.chat_session import ChatSession

        stmt = stmt.options(
            selectinload(self._model.workflow),
            selectinload(self._model.chat_session).selectinload(ChatSession.workflow),
        )

        stmt = stmt.order_by(self._model.created_at.desc()).offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        executions = result.scalars().all()

        return executions, total

    async def get_in_flight(self, project_id: UUID) -> list[Execution]:
        """
        Return executions with status QUEUED or RUNNING for the given project.

        Joins to Workflow so results are scoped to the caller's project only.
        No pagination — in-flight lists are expected to be short (bounded by
        worker concurrency). Returns rows ordered by created_at ascending
        (oldest first, so monitors see queue age naturally).

        Args:
            project_id: Project ID to scope the query to.

        Returns:
            List of Execution rows in QUEUED or RUNNING state.
        """
        from assemblix_api.database.models.workflow import Workflow

        stmt = (
            select(self._model)
            .join(Workflow, self._model.workflow_id == Workflow.id)
            .where(
                Workflow.project_id == project_id,
                self._model.status.in_([ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]),
            )
            .order_by(self._model.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_resumable(self, older_than_seconds: int) -> list[Execution]:
        """Executions stuck in QUEUED/RUNNING past the cutoff — likely orphaned by a crash.

        Uses started_at when set; falls back to created_at for QUEUED rows whose worker
        crashed before marking them RUNNING (started_at is still NULL there).
        """
        # Columns are naive UTC (TimestampMixin uses datetime.utcnow). Strip tzinfo so the
        # comparison type matches the stored values — avoids psycopg2/asyncpg type errors.
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=older_than_seconds)
        stmt = select(self._model).where(
            self._model.status.in_([ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]),
            or_(
                self._model.started_at < cutoff,
                and_(self._model.started_at.is_(None), self._model.created_at < cutoff),
            ),
        )
        return list((await self._session.scalars(stmt)).all())

    async def delete_debug_executions_older_than(self, hours: int = 1) -> int:
        """Delete debug executions older than the given number of hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        stmt = delete(self._model).where(
            self._model.is_debug == True, self._model.created_at < cutoff_time
        )

        result = await self._session.execute(stmt)
        await self._session.flush()

        return result.rowcount  # type: ignore[attr-defined]  # rowcount available on CursorResult for DML statements
