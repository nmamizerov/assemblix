# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""
Credit transaction model
"""

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Numeric

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .execution import Execution
    from .organization import Organization


class CreditTransactionType(str, Enum):
    PLAN_GRANT = "plan_grant"  # Plan-based grant
    LLM_USAGE = "llm_usage"  # LLM usage charge
    REQUEST_FEE = "request_fee"  # Per-request charge
    MANUAL_TOPUP = "manual_topup"  # Manual top-up
    REFUND = "refund"  # Refund
    VOICE_USAGE = "voice_usage"  # Text-to-speech usage charge (system keys)


class CreditTransaction(UUIDMixin, TimestampMixin, Base):
    """
    Records all credit operations: grants, charges, refunds. Amounts are stored
    in two currencies (credits and USD) for analytics.
    """

    __tablename__ = "credit_transactions"

    # Ownership
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization ID",
    )

    # Amounts in both currencies
    amount_credits: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Amount in credits (+ grant, - charge, up to 8 digits)",
    )
    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=10),
        nullable=False,
        comment="Amount in USD (+ grant, - charge, up to 10 digits)",
    )

    # Transaction type
    _type: Mapped[str] = mapped_column(
        "type",
        String(50),
        nullable=False,
        index=True,
        comment="Transaction type",
    )

    @property
    def type(self) -> CreditTransactionType:
        return CreditTransactionType(self._type)

    @type.setter
    def type(self, value: CreditTransactionType | str) -> None:
        if isinstance(value, CreditTransactionType):
            self._type = value.value
        else:
            self._type = value

    # Execution link (optional)
    execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Execution ID (for LLM_USAGE, REQUEST_FEE)",
    )

    # Description
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Transaction description",
    )

    # Analytics details
    meta: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Transaction metadata (model, tokens, provider, etc.)",
    )
    # Example meta:
    # {
    #   "model": "gpt-4o",
    #   "tokens_input": 1500,
    #   "tokens_output": 500,
    #   "provider": "openai",
    #   "used_system_key": true,
    #   "credit_value_usd_at_time": 0.0001,
    #   "margin_percent_at_time": 30,
    # }

    # Relationships
    organization: Mapped["Organization"] = relationship()
    execution: Mapped[Optional["Execution"]] = relationship()

    # Indexes
    __table_args__ = (
        Index("ix_credit_transactions_organization_id", "organization_id"),
        Index("ix_credit_transactions_type", "type"),
        Index("ix_credit_transactions_execution_id", "execution_id"),
        Index("ix_credit_transactions_created_at", "created_at"),
        Index(
            "ix_credit_transactions_org_created",
            "organization_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<CreditTransaction(id={self.id}, org_id={self.organization_id}, type={self._type}, credits={self.amount_credits})>"
