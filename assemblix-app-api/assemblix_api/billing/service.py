# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Billing and subscription plan service."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from assemblix_api.billing import limits
from assemblix_api.billing.plans import get_chat_plan_config, get_plan_config
from assemblix_api.dto.responses.billing import (
    FeaturesInfo,
    LimitsInfo,
    OrganizationUsageResponse,
    UsageInfo,
    UsageLimitInfo,
)
from assemblix_api.enums import PlanTier

if TYPE_CHECKING:
    from assemblix_api.billing.credit_service import CreditService
    from assemblix_api.billing.rate_limit_service import RateLimitService
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )
    from assemblix_api.database.repositories.workflow_repository import (
        WorkflowRepository,
    )


class BillingService:
    """Billing service: enforces subscription plan limits."""

    def __init__(
        self,
        organization_repository: OrganizationRepository,
        workflow_repository: WorkflowRepository,
        credit_service: CreditService,
        rate_limit_service: RateLimitService,
    ):
        self._org_repo = organization_repository
        self._workflow_repo = workflow_repository
        self._credit_service = credit_service
        self._rate_limit_service = rate_limit_service

    async def check_can_create_workflow(
        self, organization_id: UUID, source: str = "assemblix"
    ) -> None:
        """Check whether a new workflow (agent/widget) can be created for the source."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        current_count = await self._workflow_repo.count_organization_workflows(
            organization_id, source=source
        )

        # "chat" source is limited by the Chat plan, everything else by the Assemblix plan
        plan = organization.chat_plan if source == "chat" else organization.plan

        limits.check_agents_limit(plan, current_count, source=source)

    async def upgrade_chat_plan(self, organization_id: UUID, new_tier: PlanTier) -> None:
        """Upgrade the org Chat plan; the Assemblix plan is bumped to the same tier if lower."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        organization.chat_plan = new_tier

        tier_order = [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO, PlanTier.BUSINESS]
        if tier_order.index(organization.plan) < tier_order.index(new_tier):
            organization.plan = new_tier

        await self._org_repo.update(organization)

    async def check_and_deduct_credits(self, organization_id: UUID) -> None:
        """Pre-execution gate: enforce the RPM limit, plus a credit-balance check on FREE.

        Actual credit deduction happens after execution in WorkflowExecutor.
        """
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        # 1. Check RPM limit (for all plans)
        await self._rate_limit_service.check_rate_limit(
            organization_id=organization_id,
            plan=organization.plan,
        )

        # 2. Credit balance check only for FREE: it always uses system keys, so a minimum
        # balance is required. Paid plans may use their own keys (zero deduction).
        if organization.plan == PlanTier.FREE:
            await self._credit_service.check_balance(
                organization_id=organization_id,
                required_credits=1,
            )

    async def check_feature_available(self, organization_id: UUID, feature: str) -> None:
        """Check whether a feature is available on the org's plan."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        limits.check_feature_available(organization.plan, feature)

    async def get_organization_usage(self, organization_id: UUID) -> OrganizationUsageResponse:
        """Return the organization's resource usage and plan limits."""
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        assemblix_agents_count = await self._workflow_repo.count_organization_workflows(
            organization_id, source="assemblix"
        )
        chat_widgets_count = await self._workflow_repo.count_organization_workflows(
            organization_id, source="chat"
        )

        plan_config = get_plan_config(organization.plan)
        plan_limits = limits.get_plan_limits_info(organization.plan)
        chat_plan_config = get_chat_plan_config(organization.chat_plan)
        credits_info = await self._credit_service.get_balance(organization_id)

        return OrganizationUsageResponse(
            organization_id=str(organization_id),
            plan=organization.plan.value,
            chat_plan=organization.chat_plan.value,
            billing_period_start=organization.billing_period_start.isoformat(),
            usage=UsageInfo(
                agents=UsageLimitInfo(
                    current=assemblix_agents_count,
                    limit=plan_limits["max_agents"],
                ),
                chat_widgets=UsageLimitInfo(
                    current=chat_widgets_count,
                    limit=chat_plan_config.max_widgets,
                ),
            ),
            features=FeaturesInfo(
                project_variables=plan_limits["has_project_variables"],
                can_use_own_keys=plan_config.can_use_own_keys,
            ),
            credits=credits_info,
            limits=LimitsInfo(
                rpm_limit=plan_config.rpm_limit,
            ),
        )
