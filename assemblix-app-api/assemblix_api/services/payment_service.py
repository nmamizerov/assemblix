# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""
Payment service
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from assemblix_api.billing.credit_service import CreditService
from assemblix_api.billing.plans import get_plan_config
from assemblix_api.database.models.payment import Payment, PaymentStatus
from assemblix_api.enums import PlanTier
from assemblix_api.external.payments.factory import PaymentProviderFactory

if TYPE_CHECKING:
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )
    from assemblix_api.database.repositories.payment_repository import PaymentRepository


class PaymentService:
    """
    Payments and subscriptions service: creating subscription payments,
    handling webhook notifications, auto-renewing subscriptions, and
    activating subscriptions after payment.
    """

    def __init__(
        self,
        payment_repository: PaymentRepository,
        organization_repository: OrganizationRepository,
        credit_service: CreditService,
    ):
        self._payment_repo = payment_repository
        self._org_repo = organization_repository
        self._credit_service = credit_service
        self._provider = PaymentProviderFactory.create()

    async def create_subscription_payment(
        self,
        organization_id: UUID,
        user_email: str,
        target_plan: PlanTier,
        is_recurrent: bool = True,
    ) -> Payment:
        """
        Create a payment for changing the subscription: resolve plan price,
        persist a Payment row, initialize it with the provider, then store
        the returned payment_url. Raises ValueError if the plan or the
        organization is missing.
        """
        organization = await self._org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")

        plan_config = get_plan_config(target_plan)
        amount_rub = plan_config.price_rub
        amount_kopecks = amount_rub * 100  # Convert to kopecks.

        order_id = str(uuid4())

        description = f"Подписка {plan_config.name} для Assemblix"

        from assemblix_api.core.settings import get_settings

        provider_name = get_settings().payment_provider

        payment = await self._payment_repo.create(
            organization_id=organization_id,
            user_email=user_email,
            amount=amount_kopecks,
            description=description,
            order_id=order_id,
            target_plan=target_plan,
            is_recurrent=is_recurrent,
            provider=provider_name,
            meta={
                "plan_name": plan_config.name,
                "price_rub": amount_rub,
            },
        )

        result = await self._provider.init_payment(
            order_id=order_id,
            amount=amount_kopecks,
            description=description,
            user_email=user_email,
            is_recurrent=is_recurrent,
            receipt={
                "target_plan": target_plan.value,
                "organization_id": str(organization_id),
            },
        )

        if result.success:
            payment.external_payment_id = result.payment_id
            payment.status = (
                PaymentStatus(result.status.lower()) if result.status else PaymentStatus.NEW
            )
            # On a successful init the provider always returns a checkout URL.
            assert result.payment_url is not None
            await self._payment_repo.update_payment_url(payment, result.payment_url)

            return payment
        else:
            payment.status = PaymentStatus.REJECTED
            if payment.meta is None:
                payment.meta = {}
            payment.meta["error"] = result.error_message
            await self._payment_repo.update(payment)
            raise ValueError(f"Payment initialization failed: {result.error_message}")

    async def process_notification(self, payload: dict) -> bool:
        """
        Handle a webhook notification from the payment provider: verify the
        signature, locate the payment by PaymentId, update its status, and —
        on CONFIRMED — activate the subscription. Raises ValueError if the
        signature is invalid or the payment is not found.
        """
        if not self._provider.verify_notification(payload):
            raise ValueError("Invalid notification signature")

        parsed = self._provider.parse_notification(payload)
        payment_id = parsed.get("payment_id")
        status = parsed.get("status")
        subscription_id = parsed.get("subscription_id")

        if not payment_id:
            raise ValueError("PaymentId not found in notification")

        if not status:
            raise ValueError("Status not found in notification")

        payment_id_str = str(payment_id)

        payment = await self._payment_repo.get_by_external_payment_id(payment_id_str)
        if not payment:
            raise ValueError(f"Payment with external_id {payment_id_str} not found")

        try:
            new_status = PaymentStatus(status.lower())
        except ValueError:
            # Unknown status: store the raw value in meta and bail out.
            payment.meta = payment.meta or {}
            payment.meta["unknown_status"] = status
            await self._payment_repo.update(payment)
            return False

        if subscription_id:
            payment.meta = payment.meta or {}
            payment.meta["paddle_subscription_id"] = subscription_id

        await self._payment_repo.update_status(
            payment=payment,
            status=new_status,
            external_payment_id=payment_id_str,
        )

        if new_status == PaymentStatus.CONFIRMED:
            await self._activate_subscription(payment)

        return True

    async def _activate_subscription(self, payment: Payment) -> None:
        """
        Activate the subscription after a confirmed payment: switch the
        organization's plan and grant the plan's credits.
        """
        organization = await self._org_repo.get_by_id(payment.organization_id)
        if not organization:
            raise ValueError(f"Organization {payment.organization_id} not found")

        old_plan = organization.plan
        organization.plan = payment.target_plan
        await self._org_repo.update(organization)

        await self._credit_service.grant_plan_credits(organization.id)

        payment.meta = payment.meta or {}
        payment.meta["subscription_activated"] = True
        payment.meta["old_plan"] = old_plan.value
        payment.meta["new_plan"] = payment.target_plan.value
        await self._payment_repo.update(payment)

    async def get_payment(self, payment_id: UUID) -> Payment | None:
        return await self._payment_repo.get_by_id(payment_id)

    async def get_organization_payments(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Payment], int]:
        """Return (payments, total) for the organization's payment history."""
        payments = await self._payment_repo.get_by_organization_id(
            organization_id,
            skip=skip,
            limit=limit,
        )
        total = await self._payment_repo.count_by_organization_id(organization_id)
        return payments, total
