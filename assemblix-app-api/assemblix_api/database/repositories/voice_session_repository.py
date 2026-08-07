"""Voice session repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.voice_session import VoiceSession
from assemblix_api.database.repositories.base_repository import BaseRepository


class VoiceSessionRepository(BaseRepository[VoiceSession]):
    """Repository for the voice_sessions table."""

    def __init__(self, session: AsyncSession):
        super().__init__(VoiceSession, session)

    async def list_by_agent(
        self, voice_agent_id: UUID, *, limit: int, offset: int
    ) -> tuple[Sequence[VoiceSession], int]:
        """Calls of one agent, newest first, with the total for pagination."""
        stmt = (
            select(self._model)
            .where(self._model.voice_agent_id == voice_agent_id)
            .order_by(self._model.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)

        total = await self._session.scalar(
            select(func.count())
            .select_from(self._model)
            .where(self._model.voice_agent_id == voice_agent_id)
        )
        return result.scalars().all(), int(total or 0)
