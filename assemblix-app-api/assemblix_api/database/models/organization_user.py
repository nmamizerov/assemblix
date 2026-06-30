"""
User-organization membership model
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .organization import Organization
    from .user import User


class OrganizationUser(UUIDMixin, TimestampMixin, Base):
    """
    User-organization membership. A user may belong to several organizations.
    """

    __tablename__ = "organization_users"

    # Relations
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization ID",
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID",
    )

    # Role
    is_owner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the user is the organization owner",
    )

    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="Date the user joined the organization",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="organizations")

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_user",
        ),
        Index("ix_organization_users_organization_id", "organization_id"),
        Index("ix_organization_users_user_id", "user_id"),
        Index(
            "ix_organization_users_org_user",
            "organization_id",
            "user_id",
        ),
    )

    def __repr__(self) -> str:
        return f"<OrganizationUser(org_id={self.organization_id}, user_id={self.user_id}, is_owner={self.is_owner})>"
