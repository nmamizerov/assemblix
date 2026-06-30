"""
Credentials REST API endpoints
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_credentials_service,
    get_current_user,
    get_project_service,
)
from assemblix_api.dto.requests.credentials import (
    CredentialsCreateRequest,
    CredentialsUpdateRequest,
)
from assemblix_api.dto.responses.credentials import CredentialsResponse
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/credentials", tags=["Credentials"])


@router.get("/", response_model=list[CredentialsResponse])
async def list_credentials(
    project_id: UUID = Query(..., description="Project ID"),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    type: CredentialsType | None = Query(default=None, description="Filter by provider type"),
    current_user: User = Depends(get_current_user),
    service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    List the project's credentials, optionally filtered by provider type.

    IMPORTANT: API key values are NEVER returned, for security.
    """
    await project_service.verify_user_project_access(current_user, project_id)
    credentials = await service.get_project_credentials(
        project_id,
        skip=skip,
        limit=limit,
        type=type,
    )
    return credentials


@router.get("/{credentials_id}", response_model=CredentialsResponse)
async def get_credentials(
    credentials_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Get credentials by ID, WITHOUT the API key value.

    IMPORTANT: the API key value is NEVER returned, for security. Keys are used
    only on the backend for LLM provider calls.
    """
    credentials = await service.get_by_id(credentials_id)
    await project_service.verify_user_project_access(current_user, credentials.project_id)
    return credentials


@router.post("/", response_model=CredentialsResponse, status_code=status.HTTP_201_CREATED)
async def create_credentials(
    data: CredentialsCreateRequest,
    current_user: User = Depends(get_current_user),
    service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Create new credentials for the project.

    Multiple keys for the same provider are allowed. The API key is encrypted
    before being stored. The key value is not returned in the response, for security.
    """
    await project_service.verify_user_project_access(current_user, data.project_id)
    credentials = await service.create_credentials(project_id=data.project_id, data=data)
    return credentials


@router.patch("/{credentials_id}", response_model=CredentialsResponse)
async def update_credentials(
    credentials_id: UUID,
    data: CredentialsUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Update credentials.

    Updates the given fields; all fields are optional. The provider type cannot be
    changed. If `value` is updated it is automatically encrypted. The key value is
    not returned in the response, for security.
    """
    # Fetch credentials to resolve project_id
    credentials = await service.get_by_id(credentials_id)
    await project_service.verify_user_project_access(current_user, credentials.project_id)

    credentials = await service.update_credentials(
        credentials_id=credentials_id, project_id=credentials.project_id, data=data
    )
    return credentials


@router.delete("/{credentials_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credentials(
    credentials_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Permanently delete credentials.
    """
    # Fetch credentials to resolve project_id
    credentials = await service.get_by_id(credentials_id)
    await project_service.verify_user_project_access(current_user, credentials.project_id)
    await service.delete_credentials(credentials_id, credentials.project_id)
