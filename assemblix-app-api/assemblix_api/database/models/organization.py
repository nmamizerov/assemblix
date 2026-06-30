"""
Organization model
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Numeric

from assemblix_api.enums import PlanTier

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .organization_user import OrganizationUser
    from .payment import Payment
    from .project import Project
    from .user import User


class Organization(UUIDMixin, TimestampMixin, Base):
    """
    Organizations group users and projects. Each user has a personal
    organization (is_personal=True) created automatically on registration.
    """

    __tablename__ = "organizations"

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Organization name",
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="URL-friendly identifier",
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        default=None,
        comment="Organization description",
    )

    # Ownership
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization owner",
    )

    # Type
    is_personal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Personal organization (created on registration)",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether the organization is active",
    )

    # Billing
    _plan: Mapped[str] = mapped_column(
        "plan",
        String(50),
        default="free",
        nullable=False,
        index=True,
        comment="Organization plan tier",
    )

    @property
    def plan(self) -> PlanTier:
        return PlanTier(self._plan.lower())

    @plan.setter
    def plan(self, value: PlanTier | str) -> None:
        if isinstance(value, PlanTier):
            self._plan = value.value
        else:
            self._plan = value.lower()

    _chat_plan: Mapped[str] = mapped_column(
        "chat_plan",
        String(50),
        default="free",
        nullable=False,
        index=True,
        server_default="free",
        comment="Plan tier for chat widgets",
    )

    @property
    def chat_plan(self) -> PlanTier:
        return PlanTier(self._chat_plan.lower())

    @chat_plan.setter
    def chat_plan(self, value: PlanTier | str) -> None:
        if isinstance(value, PlanTier):
            self._chat_plan = value.value
        else:
            self._chat_plan = value.lower()

    billing_period_start: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="Billing period start date",
    )
    subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        default=None,
        comment="Subscription ID in the payment system (Stripe/YooKassa)",
    )

    # Credits
    credits_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        default=0,
        nullable=False,
        comment="Current credit balance (up to 8 decimal places)",
    )
    credits_period_start: Mapped[date] = mapped_column(
        Date,
        default=lambda: datetime.utcnow().date(),
        nullable=False,
        comment="Start date of the current credit period",
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        back_populates="owned_organizations",
        foreign_keys=[owner_id],
    )
    members: Mapped[list["OrganizationUser"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_organizations_owner_id", "owner_id"),
        Index("ix_organizations_slug", "slug"),
        Index("ix_organizations_is_active", "is_active"),
        Index("ix_organizations_is_personal", "is_personal"),
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, slug={self.slug})>"
