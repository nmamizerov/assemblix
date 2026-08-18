# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""One credit meter across system-key runs, own-key runs, and a drained balance.

Drives the real production path over HTTP (register -> API key -> credential ->
two published workflows -> execute), so the whole billing gate + deduction path
runs, not just the service layer in isolation. Fixtures (``billing_run``,
``organization_repository``, ``credit_service``) come from this directory's
``conftest.py``.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from assemblix_api.database.models.credit_transaction import CreditTransactionType


async def test_credit_lifecycle_across_runs(
    billing_run: SimpleNamespace, credit_service: Any, organization_repository: Any
) -> None:
    """System-key run charges fee+margin; own-key run charges the fee only; empty balance rejects."""
    # Arrange
    org_id = billing_run.organization_id
    await organization_repository.reissue_granted_credits(
        org_id, Decimal("5000"), period_start=None
    )

    # Act 1: system-key run (charges fee + margin on the LLM cost).
    system_resp = await billing_run.execute(use_own_key=False, cost_usd=0.01)

    # Act 2: own-key run (charges the fee only, no LLM_USAGE row).
    own_resp = await billing_run.execute(use_own_key=True, cost_usd=0.01)

    # Act 3: drain the balance, then try a third (system-key) run.
    await organization_repository.reissue_granted_credits(org_id, Decimal("0"), period_start=None)
    drained_resp = await billing_run.execute(use_own_key=False, cost_usd=0.01)

    # Assert
    assert system_resp.status_code == 200
    assert own_resp.status_code == 200
    assert drained_resp.status_code == 402

    transactions, _ = await credit_service.get_transactions(org_id)
    kinds = [t["type"] for t in transactions]
    assert kinds.count(CreditTransactionType.LLM_USAGE.value) == 1  # own-key run added none
    assert kinds.count(CreditTransactionType.REQUEST_FEE.value) == 2  # both runs paid the fee

    org = await organization_repository.get_by_id(org_id)
    assert org.credits_granted_balance >= Decimal("0")
    assert org.credits_purchased_balance >= Decimal("0")
