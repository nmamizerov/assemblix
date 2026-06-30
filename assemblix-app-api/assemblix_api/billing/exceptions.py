# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Billing system exceptions."""

from fastapi import HTTPException, status


class BillingLimitExceeded(HTTPException):
    """Plan limit exceeded. Returns 402 Payment Required."""

    def __init__(self, detail: str, limit_type: str | None = None):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
            headers={"X-Limit-Type": limit_type} if limit_type else None,
        )


class FeatureNotAvailable(HTTPException):
    """Feature not available on the current plan. Returns 403 Forbidden."""

    def __init__(self, feature: str, required_plan: str | None = None):
        detail = f"Функция '{feature}' недоступна на вашем тарифном плане"
        if required_plan:
            detail += f". Необходим план: {required_plan}"

        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers=(
                {"X-Feature": feature, "X-Required-Plan": required_plan}
                if required_plan
                else {"X-Feature": feature}
            ),
        )
