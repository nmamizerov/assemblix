# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Grant renewal and the granted/purchased split, end to end."""

from datetime import date, timedelta
from decimal import Decimal

from assemblix_api.database.models.credit_transaction import CreditTransactionType


async def test_stale_period_grants_once_and_spends_granted_first(
    billing_enabled, auth_user, db_session, credit_service, organization_repository
) -> None:
    """A 3-month-stale period grants once, keeps purchases, and is spent granted-first."""
    # Arrange
    org_id = auth_user.organization_id
    organization = await organization_repository.get_by_id(org_id)
    await organization_repository.update(organization, plan="free")
    await organization_repository.reissue_granted_credits(
        org_id, Decimal("0"), period_start=date.today() - timedelta(days=93)
    )
    await organization_repository.add_purchased_credits(org_id, Decimal("1000"))
    await db_session.flush()

    # Act
    await credit_service.ensure_current_period(org_id)

    # Assert
    org = await organization_repository.get_by_id(org_id)
    assert org.credits_granted_balance == Decimal("5000")  # Free plan, granted once not thrice
    assert org.credits_purchased_balance == Decimal("1000")
    assert org.credits_period_start > date.today() - timedelta(days=32)

    grants, _ = await credit_service.get_transactions(org_id)
    assert [t["type"] for t in grants].count(CreditTransactionType.PLAN_GRANT.value) == 1

    spent = await organization_repository.deduct_credits(org_id, Decimal("5500"))
    assert spent is True
    org = await organization_repository.get_by_id(org_id)
    assert org.credits_granted_balance == Decimal("0")
    assert org.credits_purchased_balance == Decimal("500")
