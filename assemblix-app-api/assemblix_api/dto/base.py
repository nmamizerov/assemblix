"""
Base DTO models for the API.

Accept/emit camelCase over the HTTP API while keeping snake_case in Python code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    """
    snake_case -> camelCase

    Used as the alias_generator so that incoming camelCase JSON parses into
    snake_case fields and outgoing responses serialize back to camelCase aliases.
    """

    parts = s.split("_")
    if not parts:
        return s
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)


class DTOModel(BaseModel):
    """
    Base for all DTOs (requests/responses).

    - `alias_generator`: generates camelCase aliases for snake_case fields
    - `populate_by_name`: accepts both snake_case and camelCase input
    """

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=_to_camel,
        extra="allow",
    )


class PaginatedResponse[T: DTOModel](DTOModel):
    """
    Paginated response model.

    Fields:
        data: List of items
        total: Total number of items
        page: Current page
        limit: Page size
    """

    data: list[T] = Field(description="List of items on the current page")
    total: int = Field(description="Total number of items across all pages")
    page: int = Field(description="Current page number (1-based)")
    limit: int = Field(description="Maximum number of items per page")
