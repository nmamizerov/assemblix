"""Chat message repository - database operations for chat messages."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.chat_message import ChatMessage
from assemblix_api.database.repositories.base_repository import BaseRepository
from assemblix_api.enums import MessageRole


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """Repository for the chat_messages table."""

    def __init__(self, session: AsyncSession):
        super().__init__(ChatMessage, session)

    async def get_by_chat_session_id(
        self,
        chat_session_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ChatMessage]:
        """Get chat-session messages with pagination.

        Ordered by created_at DESC (newest first) for pagination; the caller
        must reverse the result to get chronological order.
        """
        stmt = (
            select(self._model)
            .where(self._model.chat_session_id == chat_session_id)
            .order_by(self._model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create_message(
        self,
        chat_session_id: UUID,
        role: MessageRole,
        content: str,
        *,
        execution_id: UUID | None = None,
        meta_data: dict | None = None,
    ) -> ChatMessage:
        """Create a new chat message."""
        return await self.create(
            chat_session_id=chat_session_id,
            role=role,
            content=content,
            execution_id=execution_id,
            meta_data=meta_data or {},
        )
