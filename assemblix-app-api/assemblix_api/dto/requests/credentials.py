"""
Pydantic schemas for credentials requests
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.dto.base import DTOModel


class CredentialsCreateRequest(DTOModel):
    type: CredentialsType = Field(description="Provider type")
    name: str | None = Field(default=None, max_length=100, description="Name")
    value: str = Field(min_length=1, max_length=1255, description="API key")
    project_id: UUID = Field(description="Project ID")


class CredentialsUpdateRequest(DTOModel):
    name: str | None = Field(default=None, max_length=100, description="Name")
    value: str | None = Field(default=None, min_length=1, max_length=1255, description="API key")
