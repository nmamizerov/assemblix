"""
Pydantic schemas for knowledge base requests
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class KnowledgeBaseCreateRequest(DTOModel):
    project_id: UUID = Field(..., description="ID of the project this knowledge base belongs to")
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the knowledge base, must be 1-255 characters",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional description of the knowledge base's content or purpose",
    )


class KnowledgeBaseUpdateRequest(DTOModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated knowledge base name; pass null to leave unchanged",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Updated description; pass null to leave unchanged",
    )


class KnowledgeDocumentTextRequest(DTOModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Document title or filename used for identification within the knowledge base",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Plain text content of the document to be indexed in the knowledge base",
    )
