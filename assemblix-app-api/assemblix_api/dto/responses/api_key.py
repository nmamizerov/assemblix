"""
Pydantic schemas for API key responses
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from assemblix_api.dto.base import DTOModel


class APIKeyResponse(DTOModel):
    """
    API key information (without the key itself).

    The plain-text key is never returned here.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier of the API key")
    name: str = Field(description="User-defined name for the API key")
    prefix: str = Field(description="Prefix of the key for identification (e.g. 'sk_a1b2c3d4...')")
    is_active: bool = Field(
        description="Whether the API key is currently active and can be used for authentication"
    )
    last_used_at: datetime | None = Field(
        default=None,
        description="Timestamp when the API key was last used for a request",
    )
    request_count: int = Field(
        description="Total number of API requests made with this key",
    )
    created_at: datetime = Field(description="Timestamp when the API key was created")
    updated_at: datetime = Field(description="Timestamp when the API key was last updated")


class APIKeyCreatedResponse(DTOModel):
    """
    Response returned when a new API key is created.

    IMPORTANT: api_key is returned only once, at creation time — it cannot be
    retrieved again, so the user must store it.
    """

    id: UUID = Field(description="Unique identifier of the newly created API key")
    name: str = Field(description="User-defined name for the API key")
    api_key: str = Field(
        description="Full API key in plain text. Shown only ONCE at creation time — store it securely!"
    )
    prefix: str = Field(description="Prefix of the key for identification in the UI")
    created_at: datetime = Field(description="Timestamp when the API key was created")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Production API Key",
                "api_key": "sk_a1b2c3d4e5f67890123456789abcdef0",
                "prefix": "sk_a1b2c3d4...",
                "created_at": "2024-01-01T12:00:00",
            }
        }
    )


class APIKeyListResponse(DTOModel):
    """
    List of the user's API keys.
    """

    keys: list[APIKeyResponse] = Field(description="List of API keys belonging to the user")
    total: int = Field(description="Total number of API keys")
