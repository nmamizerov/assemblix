"""Notification dispatcher for technical workflow execution failures."""

from __future__ import annotations

import html
from dataclasses import dataclass
from uuid import UUID

import structlog

from assemblix_api.database.repositories.notification_channel_repository import (
    NotificationChannelRepository,
)

from .senders import get_sender

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionFailurePayload:
    """Execution-failure data for message rendering (primitives only)."""

    project_id: UUID
    execution_id: UUID
    workflow_name: str
    error_type: str | None = None
    error_message: str | None = None
    failed_node_id: str | None = None


class NotificationDispatcher:
    """Dispatches execution-failure notifications to the project's enabled channels."""

    def __init__(self, repository: NotificationChannelRepository):
        self._repository = repository

    async def notify_execution_failure(self, payload: ExecutionFailurePayload) -> None:
        channels = await self._resolve_channels(payload.project_id)
        if not channels:
            return

        message = self._render_message(payload)

        for channel in channels:
            sender = get_sender(channel.type)
            if sender is None:
                logger.warning(
                    "notification.sender_not_found",
                    channel_id=str(channel.id),
                    channel_type=channel.type.value,
                )
                continue

            # A failure on one channel must not break the workflow or the
            # delivery to the remaining channels.
            try:
                data = self._repository.decrypt_data(channel)
                await sender.send(data, message)
                logger.info(
                    "notification.sent",
                    channel_id=str(channel.id),
                    channel_type=channel.type.value,
                    execution_id=str(payload.execution_id),
                )
            except Exception:
                logger.exception(
                    "notification.send_failed",
                    channel_id=str(channel.id),
                    channel_type=channel.type.value,
                    execution_id=str(payload.execution_id),
                )

    async def _resolve_channels(self, project_id: UUID):
        return await self._repository.get_enabled_by_project(project_id)

    @staticmethod
    def _render_message(payload: ExecutionFailurePayload) -> str:
        lines = [
            "🔴 <b>Ошибка выполнения workflow</b>",
            f"<b>Workflow:</b> {html.escape(payload.workflow_name)}",
            f"<b>Execution:</b> <code>{payload.execution_id}</code>",
        ]
        if payload.error_type:
            lines.append(f"<b>Тип ошибки:</b> {html.escape(payload.error_type)}")
        if payload.failed_node_id:
            lines.append(f"<b>Нода:</b> <code>{html.escape(payload.failed_node_id)}</code>")
        if payload.error_message:
            lines.append(f"<b>Сообщение:</b>\n<pre>{html.escape(payload.error_message)}</pre>")
        return "\n".join(lines)
