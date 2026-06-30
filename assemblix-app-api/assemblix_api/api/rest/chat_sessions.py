"""
Chat Sessions REST API endpoints
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Response

from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_chat_message_service,
    get_chat_service,
    get_current_user,
    get_project_service,
)
from assemblix_api.dto.base import PaginatedResponse
from assemblix_api.dto.requests.chat_session import (
    ChatSessionFilters,
    ChatSessionUpdateNameRequest,
    SendMessageRequest,
)
from assemblix_api.dto.responses.chat_message import ChatMessageResponse
from assemblix_api.dto.responses.chat_session import (
    ChatSessionBaseResponse,
    ChatSessionDetailResponse,
)
from assemblix_api.services.chat_message_service import ChatMessageService
from assemblix_api.services.chat_service import ChatService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/chat-sessions", tags=["Chat Sessions"])


@router.get("/", response_model=PaginatedResponse[ChatSessionBaseResponse])
async def list_chat_sessions(
    project_id: UUID = Query(..., description="Project ID"),
    page: int = Query(default=1, ge=1, description="Page number (starting from 1)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    workflow_id: UUID | None = Query(default=None, description="Filter by workflow"),
    include_debug: bool = Query(
        default=False, description="Include debug sessions (excluded by default)"
    ),
    date_from: datetime | None = Query(
        default=None, description="Filter by last message date (>=)"
    ),
    date_to: datetime | None = Query(default=None, description="Filter by last message date (<=)"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    List a project's chat sessions with filtering.

    Returns basic info for each session without the message history.
    """
    await project_service.verify_user_project_access(current_user, project_id)

    filters = ChatSessionFilters(
        workflow_id=workflow_id,
        include_debug=include_debug,
        date_from=date_from,
        date_to=date_to,
    )

    chat_sessions = await service.get_project_sessions(
        project_id,
        page=page,
        limit=limit,
        filters=filters,
    )
    return chat_sessions


@router.get("/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session_detail(
    session_id: UUID = Path(..., description="ID chat session"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Get detailed chat session info including the message history.

    Returns full session info, including:
    - All session parameters (state, statistics, status)
    - The full message history (sorted by time)
    """
    project_id = await service.get_session_project_id(session_id)
    await project_service.verify_user_project_access(current_user, project_id)
    session_detail = await service.get_session_detail(
        session_id=session_id,
    )
    return session_detail


@router.patch("/{session_id}/name", response_model=ChatSessionDetailResponse)
async def rename_chat_session(
    data: ChatSessionUpdateNameRequest,
    session_id: UUID = Path(..., description="ID chat session"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Rename a chat session.

    The name field is initially null and is only set by an explicit call to this endpoint.
    """
    project_id = await service.get_session_project_id(session_id)
    await project_service.verify_user_project_access(current_user, project_id)
    return await service.rename_session(session_id, data)


@router.delete("/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: UUID = Path(..., description="ID chat session"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Delete a chat session.

    Deletes the session along with its entire message history and related executions.
    This operation is irreversible.
    """
    project_id = await service.get_session_project_id(session_id)
    await project_service.verify_user_project_access(current_user, project_id)
    await service.delete_session(session_id)
    return Response(status_code=204)


@router.post(
    "/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=201,
)
async def send_message_to_session(
    data: SendMessageRequest,
    session_id: UUID = Path(..., description="ID chat session"),
    current_user: User = Depends(get_current_user),
    message_service: ChatMessageService = Depends(get_chat_message_service),
    service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Manually add a message to a chat session.

    Adds a message to the chat history without running a workflow.
    Useful for debugging, testing, or manual conversation management.
    """
    project_id = await service.get_session_project_id(session_id)
    await project_service.verify_user_project_access(current_user, project_id)
    return await message_service.send_manual_message(session_id, data)
