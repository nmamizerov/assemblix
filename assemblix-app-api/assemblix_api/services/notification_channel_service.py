"""
Notification channel service - business logic for notification channels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.notification_channel import NotificationChannel
from assemblix_api.database.repositories.notification_channel_repository import (
    NotificationChannelRepository,
)
from assemblix_api.dto.responses.notification_channel import (
    NotificationChannelResponse,
    NotificationChannelTestResponse,
)
from assemblix_api.enums import NotificationChannelType
from assemblix_api.services.base_service import BaseService
from assemblix_api.services.notifications.senders import get_sender
from assemblix_api.services.notifications.specs import (
    mask_channel_data,
    validate_channel_data,
)

if TYPE_CHECKING:
    from assemblix_api.dto.requests.notification_channel import (
        NotificationChannelCreateRequest,
        NotificationChannelUpdateRequest,
    )

TEST_MESSAGE = "✅ Тестовое сообщение от Assemblix. Канал нотификаций настроен корректно."


class NotificationChannelService(BaseService[NotificationChannel, NotificationChannelRepository]):
    def __init__(self, repository: NotificationChannelRepository):
        super().__init__(repository, entity_name="NotificationChannel")

    async def create_channel(
        self,
        *,
        project_id: UUID,
        data: NotificationChannelCreateRequest,
    ) -> NotificationChannelResponse:
        self._validate_data(data.type, data.data)

        channel = await self.create(
            project_id=project_id,
            type=data.type,
            name=data.name,
            data=data.data,
            is_enabled=data.is_enabled,
        )
        return self._to_response(channel)

    async def update_channel(
        self,
        channel_id: UUID,
        project_id: UUID,
        *,
        data: NotificationChannelUpdateRequest,
    ) -> NotificationChannelResponse:
        channel = await self._check_ownership(channel_id, project_id)

        update_data = data.model_dump(exclude_unset=True)

        # When data is being updated, validate it against the channel's current type.
        if "data" in update_data and update_data["data"] is not None:
            self._validate_data(channel.type, update_data["data"])

        updated = await self.update(channel_id, **update_data)
        return self._to_response(updated)

    async def delete_channel(self, channel_id: UUID, project_id: UUID) -> None:
        await self._check_ownership(channel_id, project_id)
        await self.delete(channel_id)

    async def get_project_channels(self, project_id: UUID) -> list[NotificationChannelResponse]:
        channels = await self._repository.get_by_project(project_id)
        return [self._to_response(channel) for channel in channels]

    async def get_channel(self, channel_id: UUID, project_id: UUID) -> NotificationChannelResponse:
        channel = await self._check_ownership(channel_id, project_id)
        return self._to_response(channel)

    async def test_channel(
        self, channel_id: UUID, project_id: UUID
    ) -> NotificationChannelTestResponse:
        """
        Send a test message to the channel to validate its configuration.

        Never raises on a network error: returns success=False with a description
        so the UI can surface the cause.
        """
        channel = await self._check_ownership(channel_id, project_id)

        sender = get_sender(channel.type)
        if sender is None:
            return NotificationChannelTestResponse(
                success=False,
                detail=f"Тип канала {channel.type.value} не поддерживается",
            )

        try:
            data = self._repository.decrypt_data(channel)
            await sender.send(data, TEST_MESSAGE)
            return NotificationChannelTestResponse(success=True, detail=None)
        except Exception as exc:
            return NotificationChannelTestResponse(success=False, detail=str(exc))

    def _validate_data(self, channel_type: NotificationChannelType, data: dict) -> None:
        """Validate data against the channel type, converting ValueError to HTTP 400."""
        try:
            validate_channel_data(channel_type, data)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    async def _check_ownership(self, channel_id: UUID, project_id: UUID) -> NotificationChannel:
        """Ensure the channel exists and belongs to the project."""
        channel = await self.get_by_id(channel_id)
        if channel.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для работы с этим каналом",
            )
        return channel

    def _to_response(self, channel: NotificationChannel) -> NotificationChannelResponse:
        """Build the response with secret fields in `data` masked."""
        decrypted = self._repository.decrypt_data(channel)
        return NotificationChannelResponse(
            id=channel.id,
            project_id=channel.project_id,
            type=channel.type,
            name=channel.name,
            data=mask_channel_data(channel.type, decrypted),
            is_enabled=channel.is_enabled,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )
