from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import NotificationChannelType


class NotificationChannelResponse(DTOModel):
    """
    Secret fields inside `data` (e.g. bot_token) are masked and are NEVER
    returned in plaintext.
    """

    id: UUID = Field(description="Channel identifier")
    project_id: UUID = Field(description="Owner project ID")
    type: NotificationChannelType = Field(description="Notification source type")
    name: str | None = Field(default=None, description="Name")
    data: dict[str, Any] = Field(description="Channel settings (secrets are masked)")
    is_enabled: bool = Field(description="Whether the channel is enabled")
    created_at: datetime = Field(description="Creation date")
    updated_at: datetime = Field(description="Update date")


class NotificationChannelTestResponse(DTOModel):
    success: bool = Field(description="Whether the test message was sent successfully")
    detail: str | None = Field(default=None, description="Error description, if any")
