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


class UsageLimitInfo(BaseModel):
    """Current usage and its limit."""

    current: int = Field(..., description="Current usage")
    limit: int | None = Field(..., description="Limit (None = unlimited)")


class UsageInfo(BaseModel):
    """Resource usage information."""

    agents: UsageLimitInfo = Field(..., description="Agent usage")
    chat_widgets: UsageLimitInfo | None = Field(default=None, description="Chat widget usage")


class FeaturesInfo(DTOModel):
    """Available feature flags."""

    project_variables: bool = Field(..., description="Whether project variables are available")
    can_use_own_keys: bool = Field(..., description="Whether the user can use their own API keys")


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


class OrganizationUsageResponse(DTOModel):
    """Organization resource usage information."""

    organization_id: str = Field(..., description="Organization ID")
    plan: str = Field(..., description="Current plan")
    chat_plan: str = Field(default="free", description="Current Chat plan")
    billing_period_start: str = Field(..., description="Start date of the billing period")
    usage: UsageInfo = Field(..., description="Resource usage")
    features: FeaturesInfo = Field(..., description="Available features")
    credits: CreditsInfo = Field(..., description="Credit information")
    limits: LimitsInfo = Field(..., description="Plan limits")


class PlanInfoResponse(DTOModel):
    """Plan information."""

    plan: str = Field(..., description="Plan identifier")
    name: str = Field(..., description="Plan display name")
    price_rub: int = Field(..., description="Monthly price in rubles")
    max_agents: int | None = Field(..., description="Maximum number of agents (None = unlimited)")
    credits_per_month: int = Field(..., description="Number of credits per month")
    can_use_own_keys: bool = Field(..., description="Whether the user can use their own API keys")
    has_project_variables: bool = Field(..., description="Whether project variables are available")
    support_level: str = Field(..., description="Support level")
    rpm_limit: int = Field(..., description="Requests per minute limit (RPM)")


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
