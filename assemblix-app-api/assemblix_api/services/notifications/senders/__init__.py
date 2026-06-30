"""Notification senders by channel type."""

from __future__ import annotations

from assemblix_api.enums import NotificationChannelType

from .base import Sender
from .telegram import TelegramSender

_SENDERS: dict[NotificationChannelType, Sender] = {
    NotificationChannelType.TELEGRAM: TelegramSender(),
}


def get_sender(channel_type: NotificationChannelType) -> Sender | None:
    return _SENDERS.get(channel_type)


__all__ = ["Sender", "TelegramSender", "get_sender"]
