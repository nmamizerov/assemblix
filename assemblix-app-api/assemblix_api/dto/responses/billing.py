# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""
Response DTOs for billing
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from assemblix_api.dto.base import DTOModel, PaginatedResponse


class CreditsInfo(DTOModel):
    """Credit balance information."""

    credits_balance: int = Field(..., description="Current credit balance")
    plan: str = Field(..., description="Current plan")
    credits_per_month: int = Field(..., description="Credits per month granted by the plan")
    period_start: str = Field(..., description="Start date of the credit period")
    next_reset_date: str = Field(..., description="Date of the next credit reset")


class LimitsInfo(DTOModel):
    """Plan limit information."""

    rpm_limit: int = Field(..., description="Requests per minute limit (RPM)")
    concurrent_calls: int = Field(..., description="Concurrent voice call limit")


class OrganizationUsageResponse(DTOModel):
    """Organization resource usage information."""

    organization_id: str = Field(..., description="Organization ID")
    plan: str = Field(..., description="Current plan")
    billing_period_start: str = Field(..., description="Start date of the billing period")
    credits: CreditsInfo = Field(..., description="Credit information")
    limits: LimitsInfo = Field(..., description="Plan limits")


class PlanInfoResponse(DTOModel):
    """Plan information."""

    plan: str = Field(..., description="Plan identifier")
    name: str = Field(..., description="Plan display name")
    price_usd_cents: int = Field(..., description="Monthly price in USD cents")
    credits_per_month: int = Field(..., description="Number of credits per month")
    support_level: str = Field(..., description="Support level")
    rpm_limit: int = Field(..., description="Requests per minute limit (RPM)")
    concurrent_calls: int = Field(..., description="Concurrent voice call limit")


class AllPlansResponse(BaseModel):
    """List of all available plans."""

    plans: list[PlanInfoResponse] = Field(..., description="List of plans")


class CreditTransactionResponse(DTOModel):
    """Credit transaction model."""

    id: UUID = Field(description="Unique identifier of the credit transaction")
    amount_credits: float = Field(
        description="Number of credits involved in the transaction (positive for top-ups, negative for usage)"
    )
    amount_usd: float = Field(description="Equivalent USD value of the transaction")
    type: str = Field(
        description="Transaction type (e.g. 'usage', 'topup', 'refund', 'monthly_reset')"
    )
    execution_id: UUID | None = Field(
        default=None,
        description="ID of the workflow execution that triggered this transaction, if applicable",
    )
    description: str = Field(description="Human-readable description of the transaction")
    metadata: dict | None = Field(
        default=None,
        alias="meta",
        description="Additional metadata about the transaction",
    )
    created_at: datetime = Field(description="Timestamp when the transaction was recorded")


class CreditTransactionListResponse(PaginatedResponse[CreditTransactionResponse]):
    """Paginated list of credit transactions"""

    pass


class CreditPackResponse(DTOModel):
    """One-off credit pack available for purchase."""

    code: str = Field(..., description="Pack code (e.g. 's', 'm', 'l')")
    price_usd_cents: int = Field(..., description="Price in USD cents")
    credits: int = Field(..., description="Credits granted by the pack")


class CreditPacksResponse(BaseModel):
    """List of all available credit packs."""

    packs: list[CreditPackResponse] = Field(..., description="List of credit packs")
