from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class NodeTemplateResponse(DTOModel):
    id: UUID = Field(description="Unique identifier of the node template")
    project_id: UUID = Field(description="ID of the project this node template belongs to")
    name: str = Field(description="Display name of the node template")
    description: str | None = Field(
        default=None, description="Optional description of what this node template does"
    )
    config: dict = Field(
        description="Node configuration including type, parameters, and connections"
    )
    created_at: datetime = Field(description="Timestamp when the node template was created")
    updated_at: datetime = Field(description="Timestamp when the node template was last updated")
