"""
API key model for Bearer token authentication
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .project import Project


class APIKey(UUIDMixin, TimestampMixin, Base):
    """
    API keys let users authenticate via Bearer token instead of JWT. Keys are
    bcrypt-hashed and shown only once, at creation.

    Key format: sk_<32 hex chars>
    """

    __tablename__ = "api_keys"

    # Ownership
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Key Info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User-defined key name",
    )
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt hash of the API key",
    )
    prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
        comment="Key prefix for identification (sk_xxxxx...)",
    )

    # Usage Tracking
    last_used_at: Mapped[datetime | None] = mapped_column(
        default=None,
        comment="Timestamp of last key usage",
    )
    request_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Number of requests made with this key",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
        comment="Whether the key is active (can be disabled without deletion)",
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="api_keys")

    # Indexes
    __table_args__ = (
        Index("ix_api_keys_project_id_active", "project_id", "is_active"),
        Index("ix_api_keys_prefix", "prefix"),
    )

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.prefix}, active={self.is_active})>"
