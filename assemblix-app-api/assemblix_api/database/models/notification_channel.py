"""
Project notification channel model.

A channel describes WHERE to send notifications about technical workflow
execution errors (status=FAILED). Initially only Telegram is supported, but the
channel type plus an arbitrary (encrypted) `data` field allow adding new sinks
(Slack, etc.) without schema changes.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assemblix_api.enums import NotificationChannelType

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .project import Project


class NotificationChannel(UUIDMixin, TimestampMixin, Base):
    """
    Notification channel bound to a project.

    The `data` field stores an encrypted (Fernet) JSON blob with channel-specific
    settings. For Telegram this is `{"bot_token": ..., "chat_id": ...}`.
    Encryption/decryption happens in NotificationChannelRepository; the secret is
    never exposed outward.
    """

    __tablename__ = "notification_channels"

    # Ownership
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Channel definition
    type: Mapped[NotificationChannelType] = mapped_column(nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100), default=None)

    # Encrypted JSON blob with channel-specific settings (e.g. TG bot_token + chat_id)
    data: Mapped[str] = mapped_column(Text, nullable=False)

    # Status
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="notification_channels")

    def __repr__(self) -> str:
        return (
            f"<NotificationChannel(id={self.id}, type={self.type}, project_id={self.project_id})>"
        )
