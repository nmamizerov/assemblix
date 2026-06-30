# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""Payment model."""

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assemblix_api.enums import PlanTier

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .organization import Organization


class PaymentStatus(str, Enum):
    """Payment lifecycle status."""

    INIT = "init"  # created
    NEW = "new"  # sent to the bank
    FORM_SHOWED = "form_showed"  # payment form shown
    AUTHORIZED = "authorized"
    CONFIRMED = "confirmed"  # funds captured
    REJECTED = "rejected"
    REFUNDED = "refunded"
    CANCELED = "canceled"


class Payment(UUIDMixin, TimestampMixin, Base):
    """A subscription payment for an organization (supports recurrent payments)."""

    __tablename__ = "payments"

    # Ownership
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization ID",
    )

    user_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Payer email",
    )
    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Amount in minor units (kopecks)",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Payment description",
    )

    _status: Mapped[str] = mapped_column(
        "status",
        String(50),
        nullable=False,
        index=True,
        default=PaymentStatus.INIT.value,
        comment="Payment status",
    )

    @property
    def status(self) -> PaymentStatus:
        return PaymentStatus(self._status)

    @status.setter
    def status(self, value: PaymentStatus | str) -> None:
        if isinstance(value, PaymentStatus):
            self._status = value.value
        else:
            self._status = value

    external_payment_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Payment ID in the payment system",
    )

    order_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique order ID (UUID)",
    )

    _target_plan: Mapped[str] = mapped_column(
        "target_plan",
        String(50),
        nullable=False,
        comment="Target plan tier",
    )

    @property
    def target_plan(self) -> PlanTier:
        return PlanTier(self._target_plan)

    @target_plan.setter
    def target_plan(self, value: PlanTier | str) -> None:
        if isinstance(value, PlanTier):
            self._target_plan = value.value
        else:
            self._target_plan = value.lower()

    # Recurrent payments (Paddle manages renewals via webhooks).
    is_recurrent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Recurrent payment (auto-renewing subscription)",
    )

    payment_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Payment URL",
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="paddle",
        comment="Payment provider (paddle)",
    )

    meta: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional payment metadata",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        back_populates="payments",
    )

    __table_args__ = (
        Index("ix_payments_organization_id", "organization_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_external_payment_id", "external_payment_id"),
        Index("ix_payments_created_at", "created_at"),
        Index("ix_payments_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, org_id={self.organization_id}, status={self._status}, amount={self.amount})>"
