"""Notification channel repository - database operations for notification channels.

Automatically encrypts the `data` field (a JSON blob) on save and exposes a method
to decrypt it. The decrypted value is NEVER returned to the frontend.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.core.encryption import get_encryption_service
from assemblix_api.database.models.notification_channel import NotificationChannel
from assemblix_api.database.repositories.base_repository import BaseRepository


class NotificationChannelRepository(BaseRepository[NotificationChannel]):
    """Repository for the notification_channels table.

    The `data` field (dict) is serialized to JSON and encrypted before saving.
    Use decrypt_data() to retrieve the decrypted dict.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(NotificationChannel, session)
        self._encryption_service = get_encryption_service()

    async def create(self, **kwargs) -> NotificationChannel:
        """Create a channel, encrypting `data`."""
        if "data" in kwargs and kwargs["data"] is not None:
            kwargs["data"] = self._encrypt_data(kwargs["data"])
        return await super().create(**kwargs)

    async def update(self, instance: NotificationChannel, **kwargs) -> NotificationChannel:
        """Update a channel, encrypting `data` if it is provided."""
        if "data" in kwargs and kwargs["data"] is not None:
            kwargs["data"] = self._encrypt_data(kwargs["data"])
        return await super().update(instance, **kwargs)

    def _encrypt_data(self, data: dict) -> str:
        """Serialize a dict to JSON and encrypt it."""
        return self._encryption_service.encrypt(json.dumps(data))

    def decrypt_data(self, channel: NotificationChannel) -> dict:
        """Decrypt the channel's `data` into a dict.

        WARNING: backend-internal use only (notification dispatcher).
        Never send the result to the frontend!
        """
        if not channel.data:
            return {}
        return json.loads(self._encryption_service.decrypt(channel.data))

    async def get_by_project(self, project_id: UUID) -> Sequence[NotificationChannel]:
        """Get all channels of a project."""
        stmt = (
            select(self._model)
            .where(self._model.project_id == project_id)
            .order_by(self._model.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_enabled_by_project(self, project_id: UUID) -> Sequence[NotificationChannel]:
        """Get only the enabled channels of a project (for the dispatcher)."""
        stmt = select(self._model).where(
            self._model.project_id == project_id,
            self._model.is_enabled.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
