from __future__ import annotations

from typing import Any

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import NotificationChannelType


class NotificationChannelCreateRequest(DTOModel):
    type: NotificationChannelType = Field(description="Notification channel type")
    name: str | None = Field(default=None, max_length=100, description="Name")
    data: dict[str, Any] = Field(description="Channel settings (for TELEGRAM: bot_token + chat_id)")
    is_enabled: bool = Field(default=True, description="Whether the channel is enabled")


class NotificationChannelUpdateRequest(DTOModel):
    name: str | None = Field(default=None, max_length=100, description="Name")
    data: dict[str, Any] | None = Field(
        default=None, description="Channel settings (overwrite existing ones)"
    )
    is_enabled: bool | None = Field(default=None, description="Whether the channel is enabled")
