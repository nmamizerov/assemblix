# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""RPM rate limiting. Backend is in-memory (single process) or Redis (multi-replica)."""

from __future__ import annotations

from uuid import UUID

from assemblix_api.billing.exceptions import BillingLimitExceeded
from assemblix_api.billing.plans import get_plan_config
from assemblix_api.billing.rate_limit_backends import RateLimitBackend
from assemblix_api.enums import PlanTier


class RateLimitService:
    def __init__(self, backend: RateLimitBackend) -> None:
        self._backend = backend

    async def check_rate_limit(self, organization_id: UUID, plan: PlanTier) -> None:
        """Raise BillingLimitExceeded if the org exceeded its plan's requests-per-minute."""
        rpm_limit = get_plan_config(plan).rpm_limit
        allowed = await self._backend.hit(
            key=f"org:{organization_id}", limit=rpm_limit, window_seconds=60
        )
        if not allowed:
            raise BillingLimitExceeded(
                detail=f"Rate limit exceeded: more than {rpm_limit} requests per minute. "
                "Please slow down or upgrade your plan.",
                limit_type="rate_limit",
            )
