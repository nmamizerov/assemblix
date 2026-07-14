"""
Projects REST API endpoints
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from assemblix_api.billing.service import BillingService
from assemblix_api.core.auth_context import AuthContext
from assemblix_api.database.models.organization import Organization
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_auth_context,
    get_billing_service,
    get_current_organization,
    get_current_user,
    get_project_service,
)
from assemblix_api.dto.requests.project import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
)
from assemblix_api.dto.responses.project import ProjectResponse
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    current_organization: Organization = Depends(get_current_organization),
    service: ProjectService = Depends(get_project_service),
):
    """List projects of the current organization, with optional filtering."""
    # Intentional org-level access: an API key may enumerate all projects in its own organization.
    projects = await service.get_organization_projects(
        current_organization.id,
        current_user,
        skip=skip,
        limit=limit,
        is_active=is_active,
    )
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: ProjectService = Depends(get_project_service),
):
    """Get a project by ID, if the user has access to it."""
    project = await service.authorize_project_access(auth, project_id)
    return project


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    current_organization: Organization = Depends(get_current_organization),
    service: ProjectService = Depends(get_project_service),
):
    """Create a project in the user's current organization."""
    # Intentional org-level access: an API key may create projects in its own organization.
    project = await service.create_project(
        data=data,
        organization_id=current_organization.id,
        user=current_user,
    )
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    data: ProjectUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: ProjectService = Depends(get_project_service),
    billing_service: BillingService = Depends(get_billing_service),
):
    """
    Update a project.

    Updates the given fields; all fields are optional.
    """
    project = await service.authorize_project_access(auth, project_id)

    # Updating state_schema requires the project_variables feature on the current plan.
    update_data = data.model_dump(exclude_unset=True)
    if "state_schema" in update_data and update_data["state_schema"]:
        await billing_service.check_feature_available(project.organization_id, "project_variables")

    project = await service.update_project(
        project_id=project_id,
        user=auth.user,
        **update_data,
    )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: ProjectService = Depends(get_project_service),
):
    """
    Delete a project.

    Permanently deletes the project and all related data (workflows, credentials, API keys).
    """
    await service.authorize_project_access(auth, project_id)
    await service.delete_project(project_id, auth.user)
