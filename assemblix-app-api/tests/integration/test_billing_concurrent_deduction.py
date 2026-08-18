"""Concurrent deduction is atomic: a balance sufficient for N-1 admits exactly N-1."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from assemblix_api.database.repositories.organization_repository import (
    OrganizationRepository,
)


@pytest_asyncio.fixture
async def sessionmaker_on_committed_db(committed_db: Any) -> Any:
    """Sessions with a real connection each, on the engine `committed_db` pinned."""
    return async_sessionmaker(committed_db, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def committed_org_id(sessionmaker_on_committed_db: Any) -> UUID:
    """A real organization committed to the DB, so other connections can see it."""
    from assemblix_api.database.repositories.organization_user_repository import (
        OrganizationUserRepository,
    )
    from assemblix_api.database.repositories.project_repository import ProjectRepository
    from assemblix_api.database.repositories.user_repository import UserRepository
    from assemblix_api.services.user_service import UserService

    async with sessionmaker_on_committed_db() as session:
        service = UserService(
            UserRepository(session),
            OrganizationRepository(session),
            OrganizationUserRepository(session),
            ProjectRepository(session),
        )
        _, _, organization_id, _ = await service.register_and_login(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com", password="testpass123"
        )
        await session.commit()

    return organization_id


async def test_concurrent_deduction_never_oversells(
    sessionmaker_on_committed_db: Any, committed_org_id: UUID
) -> None:
    """10 parallel deductions of 100 against a balance of 900 → 9 succeed, 1 fails, balance 0."""
    # Arrange
    async with sessionmaker_on_committed_db() as setup_session:
        await OrganizationRepository(setup_session).reissue_granted_credits(
            committed_org_id, Decimal("900"), period_start=None
        )
        await setup_session.commit()

    async def deduct_once() -> bool:
        async with sessionmaker_on_committed_db() as session:
            ok = await OrganizationRepository(session).deduct_credits(
                committed_org_id, Decimal("100")
            )
            await session.commit()
            return ok

    # Act
    results = await asyncio.gather(*(deduct_once() for _ in range(10)))

    # Assert
    assert sum(1 for ok in results if ok) == 9
    async with sessionmaker_on_committed_db() as check_session:
        org = await OrganizationRepository(check_session).get_by_id(committed_org_id)
        assert org is not None
        assert org.credits_granted_balance == Decimal("0")
        assert org.credits_purchased_balance == Decimal("0")
