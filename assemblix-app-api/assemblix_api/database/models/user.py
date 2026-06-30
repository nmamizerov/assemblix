"""
User model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .organization import Organization
    from .organization_user import OrganizationUser


class User(UUIDMixin, TimestampMixin, Base):
    """
    Platform user.
    """

    __tablename__ = "users"

    # Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # OAuth fields
    auth_provider: Mapped[str | None] = mapped_column(String(50), default=None, nullable=True)
    provider_user_id: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None, nullable=True)

    # Profile
    full_name: Mapped[str | None] = mapped_column(String(255), default=None)
    company_name: Mapped[str | None] = mapped_column(String(255), default=None)

    # UTM tracking
    utm_source: Mapped[str | None] = mapped_column(
        String(255), default=None, nullable=True, comment="Traffic source"
    )
    utm_medium: Mapped[str | None] = mapped_column(
        String(255), default=None, nullable=True, comment="Marketing channel"
    )
    utm_campaign: Mapped[str | None] = mapped_column(
        String(255), default=None, nullable=True, comment="Campaign name"
    )
    utm_content: Mapped[str | None] = mapped_column(
        String(255), default=None, nullable=True, comment="Content identifier"
    )
    utm_term: Mapped[str | None] = mapped_column(
        String(255), default=None, nullable=True, comment="Search keyword"
    )

    # Onboarding data
    onboarding: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_admin: Mapped[bool] = mapped_column(default=False, comment="Administrator flag")
    is_test: Mapped[bool] = mapped_column(
        default=False, server_default="false", comment="Test user flag"
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(default=None)

    # Timestamps (from TimestampMixin)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)

    # Organization
    current_organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )

    # Relationships
    current_organization: Mapped[Optional["Organization"]] = relationship(
        foreign_keys=[current_organization_id],
    )
    owned_organizations: Mapped[list["Organization"]] = relationship(
        back_populates="owner",
        foreign_keys="Organization.owner_id",
    )
    organizations: Mapped[list["OrganizationUser"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_users_created_at", "created_at"),)
