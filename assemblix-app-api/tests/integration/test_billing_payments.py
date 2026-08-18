# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""Two confirmed webhooks: a pack tops up purchased credits, a subscription switches plan."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest_asyncio

from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.enums import PlanTier


@pytest_asyncio.fixture
async def payments_setup(
    monkeypatch: Any,
    billing_enabled: Any,
    auth_user: Any,
    db_session: Any,
    organization_repository: Any,
) -> SimpleNamespace:
    """Wires a PaymentService over a stub provider and starts the org on FREE.

    ``init_payment`` always succeeds, ``verify_notification`` always accepts, and
    ``parse_notification`` echoes a CONFIRMED status for whatever payment_id it is
    given — enough to drive ``process_notification`` end to end without a real
    Paddle account.
    """
    from assemblix_api.billing.credit_service import CreditService
    from assemblix_api.database.repositories.credit_transaction_repository import (
        CreditTransactionRepository,
    )
    from assemblix_api.database.repositories.payment_repository import PaymentRepository
    from assemblix_api.external.payments.base_provider import PaymentInitResult
    from assemblix_api.services.payment_service import PaymentService

    organization = await organization_repository.get_by_id(auth_user.organization_id)
    await organization_repository.update(organization, plan=PlanTier.FREE)

    class _StubProvider:
        async def init_payment(
            self,
            order_id: str,
            amount: int,
            description: str,
            user_email: str,
            is_recurrent: bool = False,
            receipt: dict | None = None,
        ) -> PaymentInitResult:
            return PaymentInitResult(
                success=True,
                payment_id=f"ext-{order_id}",
                payment_url="https://pay.example/checkout/test",
                status="new",
            )

        def verify_notification(self, payload: dict) -> bool:
            return True

        def parse_notification(self, payload: dict) -> dict:
            return {"payment_id": payload["payment_id"], "status": "confirmed"}

    monkeypatch.setattr(
        "assemblix_api.services.payment_service.PaymentProviderFactory.create",
        staticmethod(lambda: _StubProvider()),
    )

    credit_service = CreditService(organization_repository, CreditTransactionRepository(db_session))
    service = PaymentService(PaymentRepository(db_session), organization_repository, credit_service)

    async def create_pack(pack_code: str) -> Any:
        return await service.create_credit_pack_payment(
            auth_user.organization_id, auth_user.user.email, pack_code
        )

    async def create_subscription(target_plan: PlanTier) -> Any:
        return await service.create_subscription_payment(
            auth_user.organization_id, auth_user.user.email, target_plan
        )

    async def confirm(payment: Any) -> None:
        ok = await service.process_notification({"payment_id": payment.external_payment_id})
        assert ok is True

    return SimpleNamespace(
        organization_id=auth_user.organization_id,
        create_pack=create_pack,
        create_subscription=create_subscription,
        confirm=confirm,
    )


async def test_pack_tops_up_and_subscription_upgrades(
    payments_setup: SimpleNamespace, credit_service: Any, organization_repository: Any
) -> None:
    """A credit_pack webhook adds purchased credits; a subscription webhook changes the plan."""
    # Arrange
    org_id = payments_setup.organization_id
    pack_payment = await payments_setup.create_pack("m")
    sub_payment = await payments_setup.create_subscription(PlanTier.PRO)

    # Act 1: confirm the credit pack purchase.
    await payments_setup.confirm(pack_payment)

    # Assert 1: purchased balance moves, plan untouched.
    org = await organization_repository.get_by_id(org_id)
    assert org.credits_purchased_balance == Decimal("70000")  # pack M, untouched by the grant
    assert org.plan == PlanTier.FREE

    # Act 2: confirm the subscription payment.
    await payments_setup.confirm(sub_payment)

    # Assert 2: plan switches and the granted balance receives the Pro grant.
    org = await organization_repository.get_by_id(org_id)
    assert org.credits_purchased_balance == Decimal("70000")  # pack M, untouched by the grant
    assert org.plan == PlanTier.PRO
    assert org.credits_granted_balance == Decimal("60000")  # Pro grant on activation

    transactions, _ = await credit_service.get_transactions(org_id)
    kinds = [t["type"] for t in transactions]
    assert kinds.count(CreditTransactionType.MANUAL_TOPUP.value) == 1
    assert kinds.count(CreditTransactionType.PLAN_GRANT.value) == 1
