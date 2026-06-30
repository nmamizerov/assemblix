from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas import StateVariable


class ProjectResponse(DTOModel):
    id: UUID = Field(..., description="Project ID")
    organization_id: UUID = Field(..., description="Organization ID")
    name: str = Field(..., description="Project name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: str | None = Field(None, description="Project description")
    is_active: bool = Field(..., description="Whether the project is active")
    created_at: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Update date")
    state_schema: list[StateVariable] = Field(..., description="Project state schema")
