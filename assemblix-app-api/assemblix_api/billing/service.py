# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Billing and subscription plan service."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from assemblix_api.billing.plans import CREDIT_PACKS, CreditPack, credit_config, get_plan_config
from assemblix_api.core.settings import get_settings
from assemblix_api.dto.responses.billing import (
    CreditsInfo,
    LimitsInfo,
    OrganizationUsageResponse,
)
from assemblix_api.external.payments.factory import PaymentProviderFactory

if TYPE_CHECKING:
    from datetime import datetime

    from assemblix_api.billing.credit_service import CreditService
    from assemblix_api.billing.rate_limit_service import RateLimitService
    from assemblix_api.database.models.credit_transaction import CreditTransactionType
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )


class BillingService:
    """Billing service: credit balance, rate limits, and organization plan info."""

    def __init__(
        self,
        organization_repository: OrganizationRepository,
        credit_service: CreditService,
        rate_limit_service: RateLimitService,
    ):
        self._org_repo = organization_repository
        self._credit_service = credit_service
        self._rate_limit_service = rate_limit_service

    async def check_and_deduct_credits(self, organization_id: UUID) -> None:
        """Pre-execution gate: enforce the RPM limit, plus a fee-sized balance check.

        Actual credit deduction happens after execution in WorkflowExecutor.
        """
        if not get_settings().billing_enabled:
            return

        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        # 1. Check RPM limit (for all plans)
        await self._rate_limit_service.check_rate_limit(
            organization_id=organization_id,
            plan=organization.plan,
        )

        # 2. Every run costs at least the per-request fee, regardless of whose keys
        # are used, so every plan needs at least that much balance to start.
        await self._credit_service.check_balance(
            organization_id=organization_id,
            required_credits=credit_config.request_fee_credits,
        )

    def get_credit_packs(self) -> list[CreditPack]:
        """The packs a customer can actually buy right now.

        A pack the payment provider has no price configured for would take the user
        to a checkout that fails, so it is not offered at all; with billing off
        nothing is for sale.
        """
        if not get_settings().billing_enabled:
            return []

        provider = PaymentProviderFactory.create()
        return [pack for pack in CREDIT_PACKS.values() if provider.supports_credit_pack(pack.code)]

    async def get_credits(self, organization_id: UUID) -> CreditsInfo:
        """Delegate to CreditService: current credit balance info for the organization."""
        return await self._credit_service.get_balance(organization_id)

    async def get_credit_transactions(
        self,
        organization_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        transaction_type: CreditTransactionType | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[list[dict], int]:
        """Delegate to CreditService: paginated credit transaction history."""
        return await self._credit_service.get_transactions(
            organization_id,
            skip=skip,
            limit=limit,
            transaction_type=transaction_type,
            from_date=from_date,
            to_date=to_date,
        )

    async def get_organization_usage(self, organization_id: UUID) -> OrganizationUsageResponse:
        """Return the organization's credits and plan limits."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        plan_config = get_plan_config(organization.plan)
        credits_info = await self._credit_service.get_balance(organization_id)

        return OrganizationUsageResponse(
            organization_id=str(organization_id),
            plan=organization.plan.value,
            billing_period_start=organization.billing_period_start.isoformat(),
            credits=credits_info,
            limits=LimitsInfo(
                rpm_limit=plan_config.rpm_limit,
                concurrent_calls=plan_config.concurrent_calls,
            ),
        )
