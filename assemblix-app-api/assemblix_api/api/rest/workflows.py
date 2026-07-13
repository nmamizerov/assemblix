"""
Workflow REST API endpoints
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.dependencies import (
    get_auth_context,
    get_project_service,
    get_workflow_service,
)
from assemblix_api.dto.requests.workflow import (
    WorkflowCreateRequest,
    WorkflowMoveRequest,
    WorkflowUpdateRequest,
)
from assemblix_api.dto.responses.workflow import WorkflowBaseResponse, WorkflowResponse
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.get("/", response_model=list[WorkflowBaseResponse])
async def list_workflows(
    project_id: UUID = Query(..., description="Project ID"),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    is_published: bool | None = Query(default=None, description="Filter by published status"),
    is_template: bool | None = Query(default=None, description="Filter by template status"),
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """List project workflows with optional status filtering."""
    await project_service.authorize_project_access(auth, project_id)

    workflows = await service.get_project_workflows(
        project_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        is_published=is_published,
        is_template=is_template,
    )
    return workflows


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Get a workflow by ID.

    Returns the full workflow including nodes, edges and state.
    For drafts it also returns the list of published versions.
    """
    workflow = await service.get_by_id(workflow_id)

    # Published workflows are public; drafts require project access.
    if not workflow.is_published:
        await project_service.authorize_project_access(auth, workflow.project_id)

    return await service.get_workflow_with_versions(workflow)


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    data: WorkflowCreateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Create a new workflow."""
    language = "en"

    project = await project_service.authorize_project_access(auth, data.project_id)

    # Create the workflow, enforcing billing limits.
    workflow = await service.create_workflow(
        data=data,
        organization_id=project.organization_id,
        language=language,
        source=data.source,
    )
    return workflow


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    data: WorkflowUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Update a workflow. All fields are optional."""
    workflow = await service.get_by_id(workflow_id)
    await project_service.authorize_project_access(auth, workflow.project_id)

    workflow = await service.update_workflow(
        workflow_id=workflow_id, project_id=workflow.project_id, data=data
    )
    return workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Permanently delete a workflow and all related data."""
    workflow = await service.get_by_id(workflow_id)
    await project_service.authorize_project_access(auth, workflow.project_id)

    await service.delete_workflow(workflow_id, workflow.project_id)


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_workflow(
    workflow_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Publish a workflow.

    Creates an immutable, versioned copy of a draft. Published versions are
    used during workflow execution.

    - Workflow must be a draft (published_for_workflow_id = NULL)
    - The version number is incremented automatically
    - Published versions are cascade-deleted together with the draft
    """
    workflow = await service.get_by_id(workflow_id)
    await project_service.authorize_project_access(auth, workflow.project_id)

    published = await service.publish_workflow(workflow_id, workflow.project_id)
    return published


@router.post("/{workflow_id}/move", response_model=WorkflowResponse)
async def move_workflow(
    workflow_id: UUID,
    data: WorkflowMoveRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Move a workflow to another project.

    Moves a workflow and all its published versions to the target project.
    The user must have access to both projects.

    - Workflow must be a draft (published_for_workflow_id = NULL)
    - All published versions are moved together with the draft
    """
    workflow = await service.get_by_id(workflow_id)

    await project_service.authorize_project_access(auth, workflow.project_id)

    # Verify access to the target project and get its organization_id.
    target_project = await project_service.authorize_project_access(
        auth, data.target_project_id
    )

    return await service.move_workflow(
        workflow_id=workflow_id,
        source_project_id=workflow.project_id,
        target_project_id=data.target_project_id,
        target_organization_id=target_project.organization_id,
    )


@router.post("/{workflow_id}/copy", response_model=WorkflowResponse)
async def copy_workflow(
    workflow_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: WorkflowService = Depends(get_workflow_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Create a copy of a workflow.

    Creates a new workflow with all parameters of the source except:
    - id (newly generated)
    - slug (newly generated)
    - name (a copy suffix is appended to the source name)
    - created_at, updated_at (set to current time)
    - Execution statistics (reset)
    - The copy is always created as a draft (is_published=False, version=None)
    """
    workflow = await service.get_by_id(workflow_id)
    project = await project_service.authorize_project_access(auth, workflow.project_id)

    copied = await service.copy_workflow(workflow_id, workflow.project_id, project.organization_id)
    return copied
