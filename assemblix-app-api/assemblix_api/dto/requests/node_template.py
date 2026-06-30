from __future__ import annotations

from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class NodeTemplateCreateRequest(DTOModel):
    project_id: UUID = Field(description="Project ID")
    name: str = Field(min_length=1, max_length=255, description="Template name")
    description: str | None = Field(
        default=None, max_length=1000, description="Template description"
    )
    config: dict = Field(description="Node configuration (full node object)")


class NodeTemplateUpdateRequest(DTOModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="Template name"
    )
    description: str | None = Field(
        default=None, max_length=1000, description="Template description"
    )
    project_id: UUID | None = Field(default=None, description="Project ID")
    config: dict | None = Field(default=None, description="Node configuration (full node object)")
