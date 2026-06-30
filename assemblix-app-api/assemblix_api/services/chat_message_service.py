"""Chat message service."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.chat_message import ChatMessage
from assemblix_api.database.repositories.chat_message_repository import (
    ChatMessageRepository,
)
from assemblix_api.database.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from assemblix_api.dto.requests.chat_session import SendMessageRequest
from assemblix_api.enums import MessageRole
from assemblix_api.services.base_service import BaseService


class ChatMessageService(BaseService[ChatMessage, ChatMessageRepository]):
    """
    Service for chat messages.

    Message persistence ordering:
    1. The user message is saved (API endpoint / ChatService) BEFORE the workflow runs.
    2. The workflow runs (AgentNode reads history but does NOT save).
    3. The assistant message is saved (WorkflowExecutor / ChatService) AFTER it finishes.

    This keeps the stored history to the user<->system dialogue only, without the
    intermediate LLM calls made inside the workflow.
    """

    def __init__(
        self,
        repository: ChatMessageRepository,
        chat_session_repository: ChatSessionRepository,
    ):
        super().__init__(repository, entity_name="ChatMessage")
        self._chat_session_repository = chat_session_repository

    async def get_chat_history(
        self,
        chat_session_id: UUID,
        *,
        limit: int = 20,
    ) -> list[dict]:
        """
        Get chat history in OpenAI message format.

        Returns the last `limit` messages in chronological order (oldest first).
        The repository returns newest-first, so the result is reversed.
        """
        messages = await self._repository.get_by_chat_session_id(
            chat_session_id,
            skip=0,
            limit=limit,
        )

        messages = list(reversed(messages))

        return [
            {
                "role": msg.role.value,
                "content": msg.content,
            }
            for msg in messages
        ]

    async def save_message(
        self,
        chat_session_id: UUID,
        role: MessageRole,
        content: str,
        *,
        execution_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> ChatMessage:
        """
        Save a new message and update the session's aggregate stats
        (message_count, total_cost, last_message_at).

        Used for any role: assistant messages carry an execution_id, while
        user/system messages do not.
        """
        message = await self._repository.create_message(
            chat_session_id=chat_session_id,
            role=role,
            content=content,
            execution_id=execution_id,
            meta_data=metadata,
        )

        from decimal import Decimal

        metadata_dict = metadata or {}
        credits = metadata_dict.get("credits", 0)
        if not isinstance(credits, Decimal):
            credits = Decimal(str(credits))

        await self._chat_session_repository.increment_message_stats(
            session_id=chat_session_id,
            credits=credits,
        )

        return message

    async def send_manual_message(
        self,
        session_id: UUID,
        data: SendMessageRequest,
    ) -> ChatMessage:
        """Add a message to a chat session's history without running a workflow."""
        session = await self._chat_session_repository.get_by_id(session_id)

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session не найдена",
            )

        if not session.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя отправить сообщение в неактивную chat session",
            )

        return await self.save_message(
            chat_session_id=session_id,
            role=data.role,
            content=data.content,
            execution_id=None,
            metadata=data.meta_data,
        )
