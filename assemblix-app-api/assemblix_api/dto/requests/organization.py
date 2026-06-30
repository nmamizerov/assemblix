from __future__ import annotations

from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class OrganizationCreateRequest(DTOModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Organization name",
    )
    slug: str | None = Field(
        default=None,
        max_length=255,
        description="URL-friendly identifier (auto-generated if not provided)",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Organization description",
    )


class OrganizationUpdateRequest(DTOModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Organization name",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Organization description",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the organization is active",
    )


class SetCurrentOrganizationRequest(DTOModel):
    organization_id: UUID = Field(
        ...,
        description="ID of the organization to set as current",
    )


class AddMemberRequest(DTOModel):
    email: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Email of the user to add",
    )
    is_owner: bool = Field(
        default=False,
        description="Make the member an owner of the organization",
    )
