"""Organization repository - database operations for organizations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.organization import Organization
from assemblix_api.database.repositories.base_repository import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for the organizations table."""

    def __init__(self, session: AsyncSession):
        super().__init__(Organization, session)

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Get an organization by slug."""
        stmt = select(self._model).where(self._model.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_owner_id(
        self,
        owner_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> Sequence[Organization]:
        """Get all organizations owned by a user."""
        stmt = select(self._model).where(self._model.owner_id == owner_id)

        if is_active is not None:
            stmt = stmt.where(self._model.is_active == is_active)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def check_slug_exists(self, slug: str) -> bool:
        """Check whether a slug already exists."""
        stmt = select(self._model).where(self._model.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def deduct_credits(self, organization_id: UUID, amount: Decimal) -> bool:
        """Spend `amount`, granted part first. False when the balance is short (no write).

        Insufficiency is detected by the affected row count, not by a prior read, so
        parallel deductions cannot oversell the balance. Every right-hand side below
        reads the pre-update row, which is what lets the purchased part reference the
        old granted value.
        """
        stmt = (
            update(Organization)
            .where(
                Organization.id == organization_id,
                Organization.credits_granted_balance + Organization.credits_purchased_balance
                >= amount,
            )
            .values(
                credits_granted_balance=func.greatest(
                    Organization.credits_granted_balance - amount, 0
                ),
                credits_purchased_balance=Organization.credits_purchased_balance
                - func.greatest(amount - Organization.credits_granted_balance, 0),
            )
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1  # type: ignore[attr-defined]  # rowcount available on CursorResult for DML statements

    async def add_purchased_credits(self, organization_id: UUID, amount: Decimal) -> None:
        """Credit a purchase. Purchased credits never expire."""
        await self._session.execute(
            update(Organization)
            .where(Organization.id == organization_id)
            .values(credits_purchased_balance=Organization.credits_purchased_balance + amount)
            .execution_options(synchronize_session="fetch")
        )

    async def reissue_granted_credits(
        self, organization_id: UUID, amount: Decimal, period_start: date | None
    ) -> None:
        """Overwrite the granted part with the plan allowance; leave purchases untouched."""
        values: dict = {"credits_granted_balance": amount}
        if period_start is not None:
            values["credits_period_start"] = period_start

        await self._session.execute(
            update(Organization)
            .where(Organization.id == organization_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
