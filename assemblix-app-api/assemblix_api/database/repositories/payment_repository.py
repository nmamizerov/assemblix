# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""Payment repository."""

from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.payment import Payment, PaymentStatus
from assemblix_api.enums import PlanTier

from .base_repository import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)

    async def create(  # type: ignore[override]  # domain-specific create signature; base accepts **kwargs
        self,
        organization_id: UUID,
        user_email: str,
        amount: int,
        description: str,
        order_id: str,
        target_plan: PlanTier,
        is_recurrent: bool = False,
        provider: str = "paddle",
        meta: dict | None = None,
    ) -> Payment:
        payment = Payment(
            organization_id=organization_id,
            user_email=user_email,
            amount=amount,
            description=description,
            order_id=order_id,
            target_plan=target_plan,
            is_recurrent=is_recurrent,
            provider=provider,
            meta=meta or {},
        )
        payment.status = PaymentStatus.INIT

        self._session.add(payment)
        await self._session.flush()
        await self._session.refresh(payment)
        return payment

    async def get_by_order_id(self, order_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.order_id == order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_payment_id(self, external_payment_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.external_payment_id == external_payment_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_organization_id(
        self,
        organization_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        status: PaymentStatus | None = None,
    ) -> list[Payment]:
        conditions = [Payment.organization_id == organization_id]

        if status:
            conditions.append(Payment._status == status.value)

        stmt = (
            select(Payment)
            .where(and_(*conditions))
            .order_by(desc(Payment.created_at))
            .offset(skip)
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_organization_id(
        self,
        organization_id: UUID,
        *,
        status: PaymentStatus | None = None,
    ) -> int:
        conditions = [Payment.organization_id == organization_id]

        if status:
            conditions.append(Payment._status == status.value)

        stmt = select(Payment).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))

    async def update_status(
        self,
        payment: Payment,
        status: PaymentStatus,
        external_payment_id: str | None = None,
    ) -> Payment:
        payment.status = status

        if external_payment_id:
            payment.external_payment_id = external_payment_id

        await self._session.flush()
        await self._session.refresh(payment)
        return payment

    async def update_payment_url(self, payment: Payment, payment_url: str) -> Payment:
        payment.payment_url = payment_url
        await self._session.flush()
        await self._session.refresh(payment)
        return payment
