"""
NodeTemplate REST API endpoints
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.dependencies import (
    get_auth_context,
    get_node_template_service,
    get_project_service,
)
from assemblix_api.dto.requests.node_template import (
    NodeTemplateCreateRequest,
    NodeTemplateUpdateRequest,
)
from assemblix_api.dto.responses.node_template import NodeTemplateResponse
from assemblix_api.services.node_template_service import NodeTemplateService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/node-templates", tags=["Node Templates"])


@router.get("/", response_model=list[NodeTemplateResponse])
async def list_node_templates(
    project_id: UUID = Query(..., description="Project ID"),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    auth: AuthContext = Depends(get_auth_context),
    service: NodeTemplateService = Depends(get_node_template_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """List a project's node templates (paginated)."""
    await project_service.authorize_project_access(auth, project_id)
    templates = await service.get_project_templates(
        project_id,
        skip=skip,
        limit=limit,
    )
    return templates


@router.get("/{template_id}", response_model=NodeTemplateResponse)
async def get_node_template(
    template_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: NodeTemplateService = Depends(get_node_template_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Get a node template by ID, including its full configuration."""
    template = await service.get_by_id(template_id)
    await project_service.authorize_project_access(auth, template.project_id)
    return template


@router.post("/", response_model=NodeTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_node_template(
    data: NodeTemplateCreateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: NodeTemplateService = Depends(get_node_template_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Create a node template for a project.

    The configuration must include the full node object (id, type, position, config).
    """
    await project_service.authorize_project_access(auth, data.project_id)
    template = await service.create_node_template(project_id=data.project_id, data=data)
    return template


@router.patch("/{template_id}", response_model=NodeTemplateResponse)
async def update_node_template(
    template_id: UUID,
    data: NodeTemplateUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: NodeTemplateService = Depends(get_node_template_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Update a node template.

    Updates the given fields; all fields are optional.
    """
    template = await service.get_by_id(template_id)
    await project_service.authorize_project_access(auth, template.project_id)

    template = await service.update_node_template(
        template_id=template_id, project_id=template.project_id, data=data
    )
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node_template(
    template_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: NodeTemplateService = Depends(get_node_template_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Permanently delete a node template."""
    template = await service.get_by_id(template_id)
    await project_service.authorize_project_access(auth, template.project_id)
    await service.delete_node_template(template_id, template.project_id)
