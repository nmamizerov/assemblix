"""Chat service - business logic for chat sessions."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.chat_session import ChatSession
from assemblix_api.database.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from assemblix_api.dto.base import PaginatedResponse
from assemblix_api.dto.requests.chat_session import (
    ChatSessionFilters,
    ChatSessionUpdateNameRequest,
)
from assemblix_api.dto.responses.chat_session import (
    ChatSessionBaseResponse,
    ChatSessionDetailResponse,
)
from assemblix_api.dto.responses.workflow import WorkflowBaseResponse
from assemblix_api.services.base_service import BaseService


class ChatService(BaseService[ChatSession, ChatSessionRepository]):
    def __init__(self, repository: ChatSessionRepository):
        super().__init__(repository, entity_name="ChatSession")

    async def create_session(
        self,
        workflow_id: UUID,
        token_id: UUID | None,
        *,
        initial_state: dict | None = None,
        is_debug: bool = False,
        name: str | None = None,
    ) -> ChatSession:
        return await self.create(
            workflow_id=workflow_id,
            token_id=token_id,
            current_state=initial_state or {},
            is_active=True,
            is_debug=is_debug,
            name=name,
        )

    async def get_session_project_id(self, session_id: UUID) -> UUID:
        """Return the chat session's project_id (via workflow) for access control."""
        session = await self._repository.get_with_workflow(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session с ID {session_id} не найден",
            )
        return session.workflow.project_id

    async def get_session(
        self,
        session_id: UUID,
        project_id: UUID,
    ) -> ChatSession:
        session = await self.get_by_id(session_id)

        if session.workflow.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для доступа к этой chat session",
            )

        return session

    async def update_session_state(
        self,
        session_id: UUID,
        state_updates: dict,
    ) -> ChatSession:
        """Update the session's current_state, merging with the existing state."""
        return await self._repository.update_state(session_id, state_updates)

    async def rename_session(
        self,
        session_id: UUID,
        data: ChatSessionUpdateNameRequest,
    ) -> ChatSessionDetailResponse:
        """
        Rename a chat session.

        Updates the name, then reloads the session with messages and workflow
        so it serializes correctly into the DTO.
        """
        session = await self.get_by_id(session_id)
        await self._repository.update(session, name=data.name)

        updated = await self._repository.get_with_messages(session_id)
        return ChatSessionDetailResponse.model_validate(updated, from_attributes=True)

    async def delete_session(self, session_id: UUID) -> None:
        """
        Delete a chat session and all related data (messages, executions).

        Cascade delete is handled at the DB level (ondelete="CASCADE").
        """
        await self.delete(session_id)

    async def end_session(self, session_id: UUID) -> ChatSession:
        session = await self.get_by_id(session_id)
        if session.is_active:
            # Assuming generic update method or repository capability.
            # Since update_state uses repository custom method, I'll check if repository has general update or I should use base service update.
            # BaseService usually has update method.
            return await self.update(session_id, is_active=False)
        return session

    async def get_project_sessions(
        self,
        project_id: UUID,
        *,
        page: int = 1,
        limit: int = 100,
        filters: ChatSessionFilters | None = None,
    ) -> PaginatedResponse[ChatSessionBaseResponse]:
        skip = (page - 1) * limit
        sessions = await self._repository.get_by_project_id(
            project_id, skip=skip, limit=limit, filters=filters
        )

        session_responses = []
        for session in sessions:
            workflow = WorkflowBaseResponse.model_validate(session.workflow, from_attributes=True)

            session_dict = {k: v for k, v in session.__dict__.items() if not k.startswith("_")}
            session_dict["workflow"] = workflow

            session_responses.append(ChatSessionBaseResponse(**session_dict))

        return PaginatedResponse(
            data=session_responses,
            total=await self._repository.count_by_project_id(project_id, filters=filters),
            page=page,
            limit=limit,
        )

    async def get_session_detail(
        self,
        session_id: UUID,
    ) -> ChatSessionDetailResponse:
        session = await self._repository.get_with_messages(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ChatSession с ID {session_id} не найдена",
            )

        session_data = ChatSessionDetailResponse.model_validate(session, from_attributes=True)

        return session_data
