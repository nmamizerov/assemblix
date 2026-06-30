"""
Pydantic schemas for API key requests.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class CreateAPIKeyRequest(DTOModel):
    """
    Request to create a new API key.
    """

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Human-readable name to identify the API key",
        examples=["Production API Key", "Development Key", "Mobile App Key"],
    )
    project_id: UUID = Field(description="Project ID")
