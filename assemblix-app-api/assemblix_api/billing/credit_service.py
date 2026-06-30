# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Credit service."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from assemblix_api.billing.exceptions import BillingLimitExceeded
from assemblix_api.billing.plans import credit_config, get_plan_config
from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.dto.responses.billing import CreditsInfo

if TYPE_CHECKING:
    from assemblix_api.database.repositories.credit_transaction_repository import (
        CreditTransactionRepository,
    )
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )


class InsufficientCreditsError(BillingLimitExceeded):
    """Not enough credits to perform the operation."""

    def __init__(self, required: Decimal, available: Decimal):
        super().__init__(f"Insufficient credits. Required: {required}, Available: {available}")
        self.required = required
        self.available = available


class CreditService:
    """Manages organization credits: balance checks, deduction, grants, and history."""

    def __init__(
        self,
        organization_repository: OrganizationRepository,
        transaction_repository: CreditTransactionRepository,
    ):
        self._org_repo = organization_repository
        self._tx_repo = transaction_repository

    async def check_balance(
        self,
        organization_id: UUID,
        required_credits: int,
    ) -> None:
        """Raise InsufficientCreditsError if the org balance is below required_credits."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        if organization.credits_balance < required_credits:
            raise InsufficientCreditsError(
                required=Decimal(required_credits),
                available=organization.credits_balance,
            )

    async def deduct_for_execution(
        self,
        organization_id: UUID,
        execution_id: UUID,
        system_key_cost_usd: Decimal,
        own_key_cost_usd: Decimal,
        *,
        metadata: dict | None = None,
    ) -> dict:
        """Deduct credits for a workflow execution.

        Only system-key LLM usage is charged (with margin); own-key usage is free
        (the user pays the provider directly). No per-request fee.
        """
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        # System keys: charge with margin. Own keys: not charged.
        system_key_credits: Decimal = Decimal(0)
        if system_key_cost_usd > 0:
            system_key_credits = credit_config.usd_to_credits(system_key_cost_usd, with_margin=True)
        own_key_credits: Decimal = Decimal(0)

        # Total may be 0 when only own keys were used
        total_credits = system_key_credits
        total_usd = system_key_cost_usd

        if total_credits > 0:
            if organization.credits_balance < total_credits:
                raise InsufficientCreditsError(
                    required=total_credits,
                    available=organization.credits_balance,
                )

            organization.credits_balance -= total_credits
            await self._org_repo.update(organization)

        full_metadata = {
            "system_key_cost_usd": float(system_key_cost_usd),
            "own_key_cost_usd": float(own_key_cost_usd),
            "credit_value_usd": float(credit_config.credit_value_usd),
            "margin_multiplier": float(credit_config.margin_multiplier),
            **(metadata or {}),
        }

        # Record a transaction only when system keys were actually charged
        if system_key_credits > 0:
            await self._tx_repo.create(
                organization_id=organization_id,
                amount_credits=-system_key_credits,
                amount_usd=-system_key_cost_usd,
                type=CreditTransactionType.LLM_USAGE,
                execution_id=execution_id,
                description=f"LLM usage (system keys) for execution {execution_id}",
                meta=full_metadata,
            )

        return {
            "system_key_credits": system_key_credits,
            "own_key_credits": own_key_credits,
            "total_credits": total_credits,
            "system_key_usd": system_key_cost_usd,
            "own_key_usd": own_key_cost_usd,
            "total_usd": total_usd,
        }

    async def grant_plan_credits(
        self,
        organization_id: UUID,
    ) -> Decimal:
        """Grant the monthly credit allowance for the org's plan and reset the period."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        plan_config = get_plan_config(organization.plan)
        credits_to_grant = Decimal(plan_config.credits_per_month)

        organization.credits_balance = credits_to_grant
        organization.credits_period_start = datetime.utcnow().date()
        await self._org_repo.update(organization)

        credits_usd = credit_config.credits_to_usd(credits_to_grant)
        await self._tx_repo.create(
            organization_id=organization_id,
            amount_credits=credits_to_grant,
            amount_usd=credits_usd,
            type=CreditTransactionType.PLAN_GRANT,
            description=f"Monthly credits grant for {organization.plan.value.upper()} plan",
            meta={
                "plan": organization.plan.value,
                "credits_per_month": float(credits_to_grant),  # Decimal -> float for JSON
            },
        )

        return credits_to_grant

    async def get_balance(
        self,
        organization_id: UUID,
    ) -> CreditsInfo:
        """Return current credit balance info for the organization."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        plan_config = get_plan_config(organization.plan)
        next_reset = self._calculate_next_reset_date(organization.credits_period_start)

        return CreditsInfo(
            credits_balance=int(organization.credits_balance),
            plan=organization.plan.value,
            credits_per_month=plan_config.credits_per_month,
            period_start=organization.credits_period_start.isoformat(),
            next_reset_date=next_reset.isoformat(),
        )

    async def get_transactions(
        self,
        organization_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        transaction_type: CreditTransactionType | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[list[dict], int]:
        """Return paginated credit transaction history as (transactions, total_count)."""
        transactions = await self._tx_repo.get_by_organization_id(
            organization_id,
            skip=skip,
            limit=limit,
            transaction_type=transaction_type,
            from_date=from_date,
            to_date=to_date,
        )

        total_count = await self._tx_repo.count_by_organization_id(
            organization_id,
            transaction_type=transaction_type,
            from_date=from_date,
            to_date=to_date,
        )

        return (
            [
                {
                    "id": str(tx.id),
                    "amount_credits": tx.amount_credits,
                    "amount_usd": tx.amount_usd,
                    "type": tx.type.value,
                    "execution_id": str(tx.execution_id) if tx.execution_id else None,
                    "description": tx.description,
                    "metadata": tx.meta,
                    "created_at": tx.created_at.isoformat(),
                }
                for tx in transactions
            ],
            total_count,
        )

    def _calculate_next_reset_date(self, period_start: date) -> date:
        """Next credit reset: same day of the next month, clamped to month length."""
        year = period_start.year
        month = period_start.month + 1
        day = period_start.day

        if month > 12:
            month = 1
            year += 1

        import calendar

        max_day = calendar.monthrange(year, month)[1]
        if day > max_day:
            day = max_day

        return date(year, month, day)
