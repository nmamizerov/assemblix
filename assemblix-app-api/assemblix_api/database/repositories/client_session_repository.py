"""Client session repository - DB operations for client sessions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from assemblix_api.database.models.client_session import ClientSession
from assemblix_api.database.repositories.base_repository import BaseRepository
from assemblix_api.dto.requests.client_session import ClientSessionFilters
from assemblix_api.utils import get_typed_default_value


class ClientSessionRepository(BaseRepository[ClientSession]):
    """Repository for the client_sessions table."""

    def __init__(self, session: AsyncSession):
        super().__init__(ClientSession, session)

    async def get_by_client_id(
        self,
        project_id: UUID,
        client_id: str,
    ) -> ClientSession | None:
        """Get a client session by project_id and client_id."""
        stmt = select(self._model).where(
            self._model.project_id == project_id,
            self._model.client_id == client_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_by_client_id(
        self,
        project_id: UUID,
        client_id: str,
        initial_state: dict,
        is_debug: bool = False,
    ) -> ClientSession:
        """Get an existing client session or create a new one. initial_state is used only on creation."""
        existing = await self.get_by_client_id(project_id, client_id)
        if existing:
            return existing

        return await self.create(
            project_id=project_id,
            client_id=client_id,
            state=initial_state,
            meta_data={},
            is_active=True,
            is_debug=is_debug,
        )

    async def update_state(
        self,
        session_id: UUID,
        state_updates: dict,
    ) -> ClientSession:
        """Update the session state by merging state_updates into the existing state."""
        session = await self.get_by_id(session_id)
        if not session:
            raise ValueError(f"ClientSession {session_id} not found")

        new_state = {**session.state, **state_updates}

        return await self.update(
            session,
            state=new_state,
            last_activity_at=datetime.now(),
        )

    async def update_metadata(
        self,
        session_id: UUID,
        metadata_updates: dict,
    ) -> ClientSession:
        """Update the session metadata by merging metadata_updates into the existing metadata."""
        session = await self.get_by_id(session_id)
        if not session:
            raise ValueError(f"ClientSession {session_id} not found")

        new_metadata = {**session.meta_data, **metadata_updates}

        return await self.update(
            session,
            meta_data=new_metadata,
            last_activity_at=datetime.now(),
        )

    async def sync_schema(
        self,
        session_id: UUID,
        project_state_schema: list[dict],
    ) -> ClientSession:
        """Sync the state with variables from project.state_schema.

        Adds variables present in the schema but missing from the current state,
        using each variable's typed default value.
        """
        session = await self.get_by_id(session_id)
        if not session:
            raise ValueError(f"ClientSession {session_id} not found")

        current_state = session.state
        new_vars = {}

        for var in project_state_schema:
            var_name = var["name"]
            if var_name not in current_state:
                new_vars[var_name] = get_typed_default_value(var)

        if new_vars:
            new_state = {**current_state, **new_vars}
            return await self.update(
                session,
                state=new_state,
                last_activity_at=datetime.now(),
            )

        return session

    async def increment_execution_stats(
        self,
        session_id: UUID,
        credits: Decimal = Decimal("0"),
    ) -> None:
        """Atomically increment execution_count, add credits, and bump last_activity_at."""
        stmt = (
            update(self._model)
            .where(self._model.id == session_id)
            .values(
                execution_count=self._model.execution_count + 1,
                total_credits=self._model.total_credits + credits,
                last_activity_at=datetime.now(),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    def _build_filters(self, query: Select[Any], filters: ClientSessionFilters) -> Select[Any]:
        """Apply ClientSessionFilters to the query."""

        # include_debug: False = non-debug only, True = all (including debug)
        if not filters.include_debug:
            query = query.where(self._model.is_debug == False)

        if filters.date_from is not None:
            query = query.where(self._model.last_activity_at >= filters.date_from)
        if filters.date_to is not None:
            query = query.where(self._model.last_activity_at <= filters.date_to)

        if filters.active_only:
            query = query.where(self._model.is_active == True)

        return query

    async def get_by_project_id(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: ClientSessionFilters | None = None,
    ) -> Sequence[ClientSession]:
        """Get client sessions for a project, with filtering."""
        if filters is None:
            filters = ClientSessionFilters()

        stmt = select(self._model).where(self._model.project_id == project_id)
        stmt = self._build_filters(stmt, filters)
        stmt = stmt.offset(skip).limit(limit).order_by(self._model.last_activity_at.desc())

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_project_id(
        self,
        project_id: UUID,
        *,
        filters: ClientSessionFilters | None = None,
    ) -> int:
        """Count client sessions for a project, with filtering."""
        if filters is None:
            filters = ClientSessionFilters()

        stmt = (
            select(func.count())
            .select_from(self._model)
            .where(self._model.project_id == project_id)
        )
        stmt = self._build_filters(stmt, filters)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_debug_client_sessions_older_than(self, hours: int = 1) -> int:
        """Delete debug client sessions older than the given number of hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        stmt = delete(self._model).where(
            self._model.is_debug == True, self._model.created_at < cutoff_time
        )

        result = await self._session.execute(stmt)
        await self._session.flush()

        return result.rowcount  # type: ignore[attr-defined]  # rowcount available on CursorResult for DML statements

    async def get_with_executions(
        self,
        session_id: UUID,
    ) -> ClientSession | None:
        """Get a client session with its executions eagerly loaded."""
        stmt = (
            select(self._model)
            .where(self._model.id == session_id)
            .options(selectinload(self._model.executions))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
