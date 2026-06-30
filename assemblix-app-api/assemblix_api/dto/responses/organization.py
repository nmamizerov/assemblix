from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class OrganizationResponse(DTOModel):
    id: UUID = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: str | None = Field(None, description="Organization description")
    owner_id: UUID = Field(..., description="Organization owner ID")
    is_personal: bool = Field(..., description="Whether the organization is personal")
    is_active: bool = Field(..., description="Whether the organization is active")
    created_at: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Update date")


class OrganizationMemberResponse(DTOModel):
    id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    user_id: UUID = Field(..., description="User ID")
    full_name: str | None = Field(None, description="Full name")
    is_owner: bool = Field(..., description="Whether the member is the owner")
    joined_at: datetime = Field(..., description="Date joined the organization")


class CurrentOrganizationResponse(DTOModel):
    current_organization_id: UUID = Field(..., description="Current organization ID")
    message: str = Field(default="Текущая организация успешно изменена")
