from __future__ import annotations

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas import StateVariable


class ProjectCreateRequest(DTOModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name",
    )
    slug: str | None = Field(
        default=None,
        max_length=255,
        description="URL-friendly identifier (auto-generated if not provided)",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Project description",
    )
    state_schema: list[StateVariable] = Field(
        default_factory=list,
        description="Project state schema",
    )


class ProjectUpdateRequest(DTOModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Project name",
    )
    slug: str | None = Field(
        default=None,
        max_length=255,
        description="URL-friendly identifier",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Project description",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the project is active",
    )
    state_schema: list[StateVariable] | None = Field(
        default=None,
        description="Project state schema",
    )
