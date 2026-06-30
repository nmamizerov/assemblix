"""Chat session repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from assemblix_api.database.models.chat_session import ChatSession
from assemblix_api.database.repositories.base_repository import BaseRepository
from assemblix_api.dto.requests.chat_session import ChatSessionFilters


class ChatSessionRepository(BaseRepository[ChatSession]):
    """Repository for the chat_sessions table."""

    def __init__(self, session: AsyncSession):
        super().__init__(ChatSession, session)

    async def update_state(
        self,
        session_id: UUID,
        state_updates: dict,
    ) -> ChatSession:
        """Update current_state by merging state_updates into the existing state."""
        session = await self.get_by_id(session_id)
        if not session:
            raise ValueError(f"ChatSession {session_id} not found")

        new_state = {**session.current_state, **state_updates}

        return await self.update(
            session,
            current_state=new_state,
        )

    def _build_filters(self, query: Select[Any], filters: ChatSessionFilters) -> Select[Any]:
        """Apply ChatSessionFilters to a query."""
        if filters.workflow_id is not None:
            query = query.where(self._model.workflow_id == filters.workflow_id)

        # include_debug: False = regular sessions only, True = include debug sessions
        if not filters.include_debug:
            query = query.where(self._model.is_debug == False)

        if filters.date_from is not None:
            query = query.where(self._model.last_message_at >= filters.date_from)
        if filters.date_to is not None:
            query = query.where(self._model.last_message_at <= filters.date_to)

        return query

    async def get_by_project_id(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: ChatSessionFilters | None = None,
    ) -> Sequence[ChatSession]:
        """Get chat sessions for a project, filtered via a join with workflow."""
        from assemblix_api.database.models.workflow import Workflow

        if filters is None:
            filters = ChatSessionFilters()

        stmt = (
            select(self._model)
            .join(Workflow, self._model.workflow_id == Workflow.id)
            .where(Workflow.project_id == project_id)
            .options(selectinload(self._model.workflow))
        )

        stmt = self._build_filters(stmt, filters)

        stmt = stmt.offset(skip).limit(limit).order_by(self._model.last_message_at.desc())

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_project_id(
        self,
        project_id: UUID,
        *,
        filters: ChatSessionFilters | None = None,
    ) -> int:
        """Count chat sessions for a project, filtered via a join with workflow."""
        from assemblix_api.database.models.workflow import Workflow

        if filters is None:
            filters = ChatSessionFilters()

        stmt = (
            select(func.count())
            .select_from(self._model)
            .join(Workflow, self._model.workflow_id == Workflow.id)
            .where(Workflow.project_id == project_id)
        )

        stmt = self._build_filters(stmt, filters)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def increment_message_stats(
        self,
        session_id: UUID,
        credits: Decimal = Decimal("0"),
    ) -> None:
        """Atomically increment message_count, add credits, and set last_message_at to now."""
        stmt = (
            update(self._model)
            .where(self._model.id == session_id)
            .values(
                message_count=self._model.message_count + 1,
                total_credits=self._model.total_credits + credits,
                last_message_at=datetime.now(),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_with_messages(
        self,
        session_id: UUID,
    ) -> ChatSession | None:
        """Get a chat session with messages and workflow eagerly loaded."""
        stmt = (
            select(self._model)
            .where(self._model.id == session_id)
            .options(selectinload(self._model.messages), selectinload(self._model.workflow))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_workflow(
        self,
        session_id: UUID,
    ) -> ChatSession | None:
        """Get a chat session with workflow loaded (no messages).

        Used for access checks via workflow.project_id.
        """
        stmt = (
            select(self._model)
            .where(self._model.id == session_id)
            .options(selectinload(self._model.workflow))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_debug_chat_sessions_older_than(self, hours: int = 1) -> int:
        """Delete debug chat sessions older than the given number of hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        stmt = delete(self._model).where(
            self._model.is_debug == True, self._model.created_at < cutoff_time
        )

        result = await self._session.execute(stmt)
        await self._session.flush()

        return result.rowcount  # type: ignore[attr-defined]  # rowcount available on CursorResult for DML statements
