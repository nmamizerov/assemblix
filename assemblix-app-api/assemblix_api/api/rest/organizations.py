"""
Organizations REST API endpoints
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assemblix_api.database.models.user import User
from assemblix_api.database.repositories.user_repository import UserRepository
from assemblix_api.dependencies import (
    get_current_user,
    get_organization_service,
    get_user_repository,
    get_user_service,
)
from assemblix_api.dto.requests.organization import (
    AddMemberRequest,
    OrganizationUpdateRequest,
    SetCurrentOrganizationRequest,
)
from assemblix_api.dto.responses.organization import (
    CurrentOrganizationResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
)
from assemblix_api.services.organization_service import OrganizationService
from assemblix_api.services.user_service import UserService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
):
    """List the current user's organizations."""
    organizations = await service.get_user_organizations(
        current_user.id,
        skip=skip,
        limit=limit,
    )
    return organizations


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
):
    """Get an organization by ID if the user has access to it."""
    organization = await service.verify_user_access(current_user, organization_id)
    return organization


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: UUID,
    data: OrganizationUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
):
    """
    Update an organization

    Updates the given organization fields. Only the owner may update the organization.
    """
    await service.verify_user_access(current_user, organization_id)

    update_data = data.model_dump(exclude_unset=True)
    organization = await service.update(organization_id, **update_data)

    return organization


@router.put("/current", response_model=CurrentOrganizationResponse)
async def set_current_organization(
    data: SetCurrentOrganizationRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
    user_repository: UserRepository = Depends(get_user_repository),
):
    """
    Switch the current organization

    Sets the given organization as the user's current one, switching the working context.
    """
    await service.verify_user_access(current_user, data.organization_id)

    await user_repository.update(
        current_user,
        current_organization_id=data.organization_id,
    )

    return CurrentOrganizationResponse(current_organization_id=data.organization_id)


@router.get("/{organization_id}/members", response_model=list[OrganizationMemberResponse])
async def get_organization_members(
    organization_id: UUID,
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
):
    """
    List organization members

    Returns all members of the organization with their details.
    Available to any member of the organization.
    """
    await service.verify_user_access(current_user, organization_id)

    members = await service.get_organization_members_with_details(
        organization_id,
        skip=skip,
        limit=limit,
    )

    return members


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_organization_member(
    organization_id: UUID,
    data: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
    user_service: UserService = Depends(get_user_service),
):
    """
    Add a member to an organization

    Adds a user by email to the organization. Only the owner may add members.
    """
    await service.verify_user_access(current_user, organization_id)

    user_to_add = await user_service.get_by_email(data.email)
    if not user_to_add:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с email '{data.email}' не найден",
        )

    await service.add_member(
        organization_id=organization_id,
        user_id=user_to_add.id,
        requester_id=current_user.id,
        is_owner=data.is_owner,
    )

    return OrganizationMemberResponse(
        id=user_to_add.id,
        user_id=user_to_add.id,
        email=user_to_add.email,
        full_name=user_to_add.full_name,
        is_owner=data.is_owner,
        joined_at=datetime.utcnow(),
    )


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_organization_member(
    organization_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
):
    """
    Remove a member from an organization

    Removes a user from the organization. Only the owner may remove members.
    The organization owner cannot be removed.
    """
    await service.verify_user_access(current_user, organization_id)

    await service.remove_member(
        organization_id=organization_id,
        user_id=user_id,
        requester_id=current_user.id,
    )
