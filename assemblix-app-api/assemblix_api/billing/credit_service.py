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
from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.dto.responses.billing import CreditsInfo

if TYPE_CHECKING:
    from assemblix_api.database.models.organization import Organization
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
        required_credits: Decimal,
    ) -> None:
        """Raise InsufficientCreditsError if the org balance is below required_credits."""
        await self.ensure_current_period(organization_id)

        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        if organization.credits_balance < required_credits:
            raise InsufficientCreditsError(
                required=required_credits,
                available=organization.credits_balance,
            )

    async def deduct_for_execution(
        self,
        organization_id: UUID,
        execution_id: UUID,
        system_key_cost_usd: Decimal,
        own_key_cost_usd: Decimal,
        *,
        system_voice_cost_usd: Decimal = Decimal(0),
        own_voice_cost_usd: Decimal = Decimal(0),
        metadata: dict | None = None,
    ) -> dict:
        """Deduct credits for a workflow execution.

        Every execution pays the fixed per-request fee, regardless of whose keys are
        used. System-key LLM usage and system-key voice (TTS) usage are additionally
        charged with margin; own-key usage is free (the user pays the provider
        directly) beyond that fee.
        """
        if not get_settings().billing_enabled:
            return {"total_credits": Decimal(0), "fee_credits": Decimal(0)}

        await self.ensure_current_period(organization_id)

        fee_credits = credit_config.request_fee_credits
        system_key_credits: Decimal = (
            credit_config.usd_to_credits(system_key_cost_usd, with_margin=True)
            if system_key_cost_usd > 0
            else Decimal(0)
        )
        voice_credits: Decimal = (
            credit_config.usd_to_credits(system_voice_cost_usd, with_margin=True)
            if system_voice_cost_usd > 0
            else Decimal(0)
        )
        total_credits = fee_credits + system_key_credits + voice_credits
        total_usd = system_key_cost_usd + system_voice_cost_usd

        # Atomic: insufficiency is reported by the repository (no row written), so
        # parallel executions cannot spend the same credits twice, and a partial
        # charge (fee without margin, or vice versa) is impossible.
        if not await self._org_repo.deduct_credits(organization_id, total_credits):
            organization = await self._org_repo.get_by_id(organization_id)
            raise InsufficientCreditsError(
                required=total_credits,
                available=organization.credits_balance if organization else Decimal(0),
            )

        full_metadata = {
            "system_key_cost_usd": float(system_key_cost_usd),
            "own_key_cost_usd": float(own_key_cost_usd),
            "own_voice_cost_usd": float(own_voice_cost_usd),
            "credit_value_usd": float(credit_config.credit_value_usd),
            "margin_multiplier": float(credit_config.margin_multiplier),
            **(metadata or {}),
        }

        # The per-request fee is charged unconditionally.
        await self._tx_repo.create(
            organization_id=organization_id,
            amount_credits=-fee_credits,
            amount_usd=-credit_config.request_fee_usd,
            type=CreditTransactionType.REQUEST_FEE,
            execution_id=execution_id,
            description=f"Platform fee for execution {execution_id}",
            meta=full_metadata,
        )

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

        # Voice (TTS) usage is itemized separately from LLM usage
        if voice_credits > 0:
            await self._tx_repo.create(
                organization_id=organization_id,
                amount_credits=-voice_credits,
                amount_usd=-system_voice_cost_usd,
                type=CreditTransactionType.VOICE_USAGE,
                execution_id=execution_id,
                description=f"Voice (TTS) usage for execution {execution_id}",
                meta={"system_voice_cost_usd": float(system_voice_cost_usd), **(metadata or {})},
            )

        return {
            "fee_credits": fee_credits,
            "system_key_credits": system_key_credits,
            "own_key_credits": Decimal(0),
            "total_credits": total_credits,
            "system_key_usd": system_key_cost_usd,
            "own_key_usd": own_key_cost_usd,
            "total_usd": total_usd,
        }

    async def ensure_current_period(self, organization_id: UUID) -> None:
        """Apply the monthly grant if the period has lapsed. Idempotent within a period.

        No-op while billing is disabled: self-host orgs sit on the unlimited BUSINESS
        plan and never need a grant. The period rolls forward by whole months (not to
        today's date) so several stale months still re-issue exactly one allowance
        rather than accumulating one per elapsed month.
        """
        if not get_settings().billing_enabled:
            return

        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        today = date.today()
        next_period = self._add_months(organization.credits_period_start, 1)
        if next_period > today:
            return

        months_elapsed = self._whole_months_between(organization.credits_period_start, today)
        new_period_start = self._add_months(organization.credits_period_start, months_elapsed)
        await self._grant(organization, new_period_start)

    async def _grant(self, organization: Organization, period_start: date) -> None:
        """Re-issue the granted part of the balance for `period_start` and record it."""
        plan_config = get_plan_config(organization.plan)
        credits_to_grant = Decimal(plan_config.credits_per_month)

        await self._org_repo.reissue_granted_credits(
            organization.id, credits_to_grant, period_start=period_start
        )
        await self._tx_repo.create(
            organization_id=organization.id,
            amount_credits=credits_to_grant,
            amount_usd=credit_config.credits_to_usd(credits_to_grant),
            type=CreditTransactionType.PLAN_GRANT,
            description=f"Monthly credits grant for {organization.plan.value.upper()} plan",
            meta={
                "plan": organization.plan.value,
                "credits_per_month": float(credits_to_grant),  # Decimal -> float for JSON
            },
        )

    async def grant_plan_credits(self, organization_id: UUID) -> Decimal:
        """Force a grant and restart the period. Used when a subscription activates."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")
        await self._grant(organization, date.today())
        return Decimal(get_plan_config(organization.plan).credits_per_month)

    @staticmethod
    def _add_months(start: date, months: int) -> date:
        """`start` shifted forward by whole `months`, clamped to the target month's length."""
        import calendar

        month_index = start.month - 1 + months
        year = start.year + month_index // 12
        month = month_index % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @classmethod
    def _whole_months_between(cls, start: date, end: date) -> int:
        """Number of whole calendar months between `start` and `end` (end >= start)."""
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if cls._add_months(start, months) > end:
            months -= 1
        return months

    async def get_balance(
        self,
        organization_id: UUID,
    ) -> CreditsInfo:
        """Return current credit balance info for the organization."""
        await self.ensure_current_period(organization_id)

        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        plan_config = get_plan_config(organization.plan)

        return CreditsInfo(
            credits_balance=int(organization.credits_balance),
            credits_granted=int(organization.credits_granted_balance),
            credits_purchased=int(organization.credits_purchased_balance),
            plan=organization.plan.value,
            credits_per_month=plan_config.credits_per_month,
            period_start=organization.credits_period_start.isoformat(),
            next_reset=self._add_months(organization.credits_period_start, 1).isoformat(),
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
