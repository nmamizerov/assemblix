"""Credit transaction repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.credit_transaction import (
    CreditTransaction,
    CreditTransactionType,
)
from assemblix_api.database.repositories.base_repository import BaseRepository


class CreditTransactionRepository(BaseRepository[CreditTransaction]):
    """Repository for the credit_transactions table."""

    def __init__(self, session: AsyncSession):
        super().__init__(CreditTransaction, session)

    async def get_by_organization_id(
        self,
        organization_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        transaction_type: CreditTransactionType | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> Sequence[CreditTransaction]:
        """Get transactions for an organization."""
        stmt = select(self._model).where(self._model.organization_id == organization_id)

        if transaction_type is not None:
            stmt = stmt.where(self._model._type == transaction_type.value)

        if from_date is not None:
            stmt = stmt.where(self._model.created_at >= from_date)

        if to_date is not None:
            stmt = stmt.where(self._model.created_at <= to_date)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_organization_id(
        self,
        organization_id: UUID,
        *,
        transaction_type: CreditTransactionType | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        """Count transactions for an organization with filters."""
        stmt = (
            select(func.count())
            .select_from(self._model)
            .where(self._model.organization_id == organization_id)
        )

        if transaction_type is not None:
            stmt = stmt.where(self._model._type == transaction_type.value)

        if from_date is not None:
            stmt = stmt.where(self._model.created_at >= from_date)

        if to_date is not None:
            stmt = stmt.where(self._model.created_at <= to_date)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_execution_id(
        self,
        execution_id: UUID,
    ) -> Sequence[CreditTransaction]:
        """Get transactions by execution_id."""
        stmt = (
            select(self._model)
            .where(self._model.execution_id == execution_id)
            .order_by(self._model.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_total_spent(
        self,
        organization_id: UUID,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> Decimal:
        """Get the total amount of spent credits as a positive number."""
        stmt = select(func.sum(self._model.amount_credits)).where(
            and_(
                self._model.organization_id == organization_id,
                self._model.amount_credits < 0,  # debits only
            )
        )

        if from_date is not None:
            stmt = stmt.where(self._model.created_at >= from_date)

        if to_date is not None:
            stmt = stmt.where(self._model.created_at <= to_date)

        result = await self._session.execute(stmt)
        total = result.scalar_one_or_none()
        return abs(total) if total else Decimal(0)

    async def get_total_granted(
        self,
        organization_id: UUID,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> Decimal:
        """Get the total amount of granted credits."""
        stmt = select(func.sum(self._model.amount_credits)).where(
            and_(
                self._model.organization_id == organization_id,
                self._model.amount_credits > 0,  # credits only
            )
        )

        if from_date is not None:
            stmt = stmt.where(self._model.created_at >= from_date)

        if to_date is not None:
            stmt = stmt.where(self._model.created_at <= to_date)

        result = await self._session.execute(stmt)
        total = result.scalar_one_or_none()
        return total if total else Decimal(0)
