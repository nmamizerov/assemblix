"""Voice agent repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.voice_agent import VoiceAgent
from assemblix_api.database.repositories.base_repository import BaseRepository


class VoiceAgentRepository(BaseRepository[VoiceAgent]):
    """Repository for the voice_agents table."""

    def __init__(self, session: AsyncSession):
        super().__init__(VoiceAgent, session)

    async def get_by_project_id(self, project_id: UUID) -> Sequence[VoiceAgent]:
        """Get all voice agents of a project, newest first."""
        stmt = (
            select(self._model)
            .where(self._model.project_id == project_id)
            .order_by(self._model.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
