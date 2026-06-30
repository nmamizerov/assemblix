"""Client session service - business logic for client sessions."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.client_session import ClientSession
from assemblix_api.database.repositories.client_session_repository import (
    ClientSessionRepository,
)
from assemblix_api.dto.requests.client_session import ClientSessionFilters
from assemblix_api.services.base_service import BaseService


class ClientSessionService(BaseService[ClientSession, ClientSessionRepository]):
    def __init__(self, repository: ClientSessionRepository):
        super().__init__(repository, entity_name="ClientSession")

    async def get_or_create_by_client_id(
        self,
        project_id: UUID,
        client_id: str,
        initial_state: dict,
        is_debug: bool = False,
    ) -> ClientSession:
        """Get an existing client session or create a new one (initial_state is used only on create)."""
        return await self._repository.get_or_create_by_client_id(
            project_id=project_id,
            client_id=client_id,
            initial_state=initial_state,
            is_debug=is_debug,
        )

    async def get_by_client_id(
        self,
        project_id: UUID,
        client_id: str,
    ) -> ClientSession | None:
        return await self._repository.get_by_client_id(project_id, client_id)

    async def get_session(
        self,
        session_id: UUID,
        project_id: UUID,
    ) -> ClientSession:
        """Get a client session, ensuring it belongs to the given project."""
        session = await self.get_by_id(session_id)

        if session.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для доступа к этой client session",
            )

        return session

    async def update_state(
        self,
        session_id: UUID,
        state_updates: dict,
    ) -> ClientSession:
        """Update the project state (merged into the existing state)."""
        return await self._repository.update_state(session_id, state_updates)

    async def update_metadata(
        self,
        session_id: UUID,
        metadata_updates: dict,
    ) -> ClientSession:
        """Update metadata (merged into the existing metadata)."""
        return await self._repository.update_metadata(session_id, metadata_updates)

    async def sync_schema(
        self,
        session_id: UUID,
        project_state_schema: list[dict],
    ) -> ClientSession:
        """Sync the state with project.state_schema.

        Adds variables present in the schema but missing from the current state,
        using their default values from the schema.
        """
        return await self._repository.sync_schema(session_id, project_state_schema)

    async def increment_execution_stats(
        self,
        session_id: UUID,
        credits: Decimal = Decimal("0"),
    ) -> None:
        await self._repository.increment_execution_stats(
            session_id=session_id,
            credits=credits,
        )

    async def get_sessions_by_project(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: ClientSessionFilters | None = None,
    ) -> tuple[Sequence[ClientSession], int]:
        """List a project's client sessions with pagination; returns (sessions, total count)."""
        sessions = await self._repository.get_by_project_id(
            project_id=project_id,
            skip=skip,
            limit=limit,
            filters=filters,
        )
        total = await self._repository.count_by_project_id(
            project_id=project_id,
            filters=filters,
        )
        return sessions, total

    async def get_with_executions(
        self,
        session_id: UUID,
    ) -> ClientSession | None:
        """Get a client session with its executions eagerly loaded."""
        return await self._repository.get_with_executions(session_id)

    async def deactivate_session(
        self,
        session_id: UUID,
        project_id: UUID,
    ) -> ClientSession:
        """Deactivate a client session (scoped to the given project)."""
        session = await self.get_session(session_id, project_id)
        return await self.update(session.id, is_active=False)
