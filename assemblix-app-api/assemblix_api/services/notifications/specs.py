"""
Per-type field specs for notification channels.

Single source of truth for which fields are required per channel type and which
are secret (masked in API responses). Adding a new source means adding an entry
here plus a new sender.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from assemblix_api.enums import NotificationChannelType

MASK = "***"


@dataclass(frozen=True)
class ChannelFieldSpec:
    required: tuple[str, ...] = ()
    secret: tuple[str, ...] = field(default_factory=tuple)


CHANNEL_FIELD_SPECS: dict[NotificationChannelType, ChannelFieldSpec] = {
    NotificationChannelType.TELEGRAM: ChannelFieldSpec(
        required=("bot_token", "chat_id"),
        secret=("bot_token",),
    ),
}


def validate_channel_data(channel_type: NotificationChannelType, data: dict) -> None:
    """
    Check that `data` contains all required non-empty fields for the type.

    Raises ValueError if the type is unsupported or fields are missing/empty.
    """
    spec = CHANNEL_FIELD_SPECS.get(channel_type)
    if spec is None:
        raise ValueError(f"Неподдерживаемый тип канала: {channel_type.value}")

    missing = [key for key in spec.required if not str(data.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Для канала {channel_type.value} обязательны поля: {', '.join(missing)}")


def mask_channel_data(channel_type: NotificationChannelType, data: dict) -> dict:
    spec = CHANNEL_FIELD_SPECS.get(channel_type)
    secret_keys = set(spec.secret) if spec else set()
    return {key: (MASK if key in secret_keys and value else value) for key, value in data.items()}
