"""
Client Sessions REST API endpoints
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_chat_service,
    get_client_session_service,
    get_current_user,
    get_execution_service,
    get_project_service,
)
from assemblix_api.dto.base import PaginatedResponse
from assemblix_api.dto.requests.client_session import (
    ClientSessionFilters,
    UpdateClientSessionMetadataRequest,
)
from assemblix_api.dto.requests.execution import ExecutionFilters
from assemblix_api.dto.responses.chat_session import ChatSessionBaseResponse
from assemblix_api.dto.responses.client_session import (
    ClientSessionBaseResponse,
)
from assemblix_api.dto.responses.execution import ExecutionInfoResponse
from assemblix_api.services.chat_service import ChatService
from assemblix_api.services.client_session_service import ClientSessionService
from assemblix_api.services.execution_service import ExecutionService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Client Sessions"])


@router.get(
    "/{project_id}/client-sessions",
    response_model=PaginatedResponse[ClientSessionBaseResponse],
)
async def list_client_sessions(
    project_id: UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, ge=1, le=100, description="Page size"),
    active_only: bool = Query(default=False, description="Active sessions only"),
    include_debug: bool = Query(
        default=False, description="Include debug sessions (excluded by default)"
    ),
    date_from: datetime | None = Query(
        default=None, description="Filter by last activity date (>=)"
    ),
    date_to: datetime | None = Query(default=None, description="Filter by last activity date (<=)"),
    current_user: User = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
):
    """List a project's client sessions with pagination and filtering."""
    await project_service.verify_user_project_access(current_user, project_id)

    offset = (page - 1) * limit

    filters = ClientSessionFilters(
        include_debug=include_debug,
        date_from=date_from,
        date_to=date_to,
        active_only=active_only,
    )

    sessions, total = await client_session_service.get_sessions_by_project(
        project_id=project_id,
        skip=offset,
        limit=limit,
        filters=filters,
    )

    data = [
        ClientSessionBaseResponse(
            id=session.id,
            project_id=session.project_id,
            client_id=session.client_id,
            state=session.state,
            metadata=session.meta_data,
            execution_count=session.execution_count,
            total_credits=float(session.total_credits),
            is_active=session.is_active,
            last_activity_at=session.last_activity_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        for session in sessions
    ]

    return PaginatedResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{project_id}/client-sessions/{client_id}",
    response_model=ClientSessionBaseResponse,
)
async def get_client_session(
    project_id: UUID,
    client_id: str,
    current_user: User = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
):
    """Get a single client session."""
    await project_service.verify_user_project_access(current_user, project_id)

    session = await client_session_service.get_by_client_id(project_id, client_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client session с client_id={client_id} не найдена",
        )

    return ClientSessionBaseResponse(
        id=session.id,
        project_id=session.project_id,
        client_id=session.client_id,
        state=session.state,
        metadata=session.meta_data,
        execution_count=session.execution_count,
        total_credits=float(session.total_credits),
        is_active=session.is_active,
        last_activity_at=session.last_activity_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get(
    "/{project_id}/client-sessions/{client_id}/executions",
    response_model=PaginatedResponse[ExecutionInfoResponse],
)
async def list_client_session_executions(
    project_id: UUID,
    client_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """List executions for a client session."""
    await project_service.verify_user_project_access(current_user, project_id)

    session = await client_session_service.get_by_client_id(project_id, client_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client session с client_id={client_id} не найдена",
        )

    offset = (page - 1) * limit

    executions, total = await execution_service.get_executions_list(
        project_id=project_id,
        offset=offset,
        limit=limit,
        filters=ExecutionFilters(client_session_id=session.id),
    )

    return PaginatedResponse(
        data=executions,
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{project_id}/client-sessions/{client_id}/chat-sessions",
    response_model=PaginatedResponse[ChatSessionBaseResponse],
)
async def list_client_chat_sessions(
    project_id: UUID,
    client_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
    execution_service: ExecutionService = Depends(get_execution_service),
    chat_service: ChatService = Depends(get_chat_service),
):
    """List chat sessions for a client_id (unique chat sessions from its executions)."""
    await project_service.verify_user_project_access(current_user, project_id)

    session = await client_session_service.get_by_client_id(project_id, client_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client session с client_id={client_id} не найдена",
        )

    # Large limit to fetch all executions for this client_session.
    executions, _ = await execution_service.get_executions_list(
        project_id=project_id,
        offset=0,
        limit=1000,
        filters=ExecutionFilters(client_session_id=session.id),
    )

    chat_session_ids = set()
    for execution in executions:
        if execution.chat_session_id:
            chat_session_ids.add(execution.chat_session_id)

    chat_sessions = []
    for chat_session_id in chat_session_ids:
        try:
            chat_session = await chat_service.get_by_id(chat_session_id)
            if chat_session:
                chat_sessions.append(chat_session)
        # Intentionally skip deleted/inaccessible sessions.
        except Exception:  # nosec B110
            pass

    offset = (page - 1) * limit
    total = len(chat_sessions)
    paginated_sessions = chat_sessions[offset : offset + limit]

    data = [
        ChatSessionBaseResponse.model_validate(session, from_attributes=True)
        for session in paginated_sessions
    ]

    return PaginatedResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
    )


@router.patch(
    "/{project_id}/client-sessions/{client_id}/metadata",
    response_model=ClientSessionBaseResponse,
)
async def update_client_session_metadata(
    project_id: UUID,
    client_id: str,
    request: UpdateClientSessionMetadataRequest,
    current_user: User = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
):
    """Update client session metadata."""
    await project_service.verify_user_project_access(current_user, project_id)

    session = await client_session_service.get_by_client_id(project_id, client_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client session с client_id={client_id} не найдена",
        )

    updated_session = await client_session_service.update_metadata(
        session_id=session.id,
        metadata_updates=request.metadata,
    )

    return ClientSessionBaseResponse(
        id=updated_session.id,
        project_id=updated_session.project_id,
        client_id=updated_session.client_id,
        state=updated_session.state,
        metadata=updated_session.meta_data,
        execution_count=updated_session.execution_count,
        total_credits=float(updated_session.total_credits),
        is_active=updated_session.is_active,
        last_activity_at=updated_session.last_activity_at,
        created_at=updated_session.created_at,
        updated_at=updated_session.updated_at,
    )


@router.delete(
    "/{project_id}/client-sessions/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_client_session(
    project_id: UUID,
    client_id: str,
    current_user: User = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
):
    """Deactivate a client session."""
    await project_service.verify_user_project_access(current_user, project_id)

    session = await client_session_service.get_by_client_id(project_id, client_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client session с client_id={client_id} не найдена",
        )

    await client_session_service.deactivate_session(session.id, project_id)
