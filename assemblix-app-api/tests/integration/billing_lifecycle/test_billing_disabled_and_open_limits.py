# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""No plan blocks building — and with billing off, nothing is metered at all.

The first case runs with billing **on** (a Free organisation, which is the plan
that used to cap agents); only the second turns billing off.

Fixtures (``billing_run``, ``credit_service``, ``billing_disabled``) come from
this directory's ``conftest.py`` / the global fixture plugins.
"""

from __future__ import annotations

from assemblix_api.database.models.credit_transaction import CreditTransactionType


async def test_free_plan_builds_freely_and_uses_own_keys(
    billing_run, api_client, credit_service
) -> None:
    """Free creates five workflows and runs on its own credential, not the system key."""
    # Arrange
    payloads = [{"name": f"Agent {i}", "projectId": str(billing_run.project_id)} for i in range(5)]

    # Act
    responses = [
        await api_client.post("/api/workflows/", json=p, headers=billing_run.jwt_headers)
        for p in payloads
    ]

    # Assert
    assert [r.status_code for r in responses] == [201] * 5
    used = await billing_run.execute(use_own_key=True, cost_usd=0.01)
    assert used.status_code == 200
    # Own-key runs pay the platform fee and nothing else: an LLM_USAGE row would mean
    # the run had fallen back to the system key.
    transactions, _ = await credit_service.get_transactions(billing_run.organization_id)
    kinds = [t["type"] for t in transactions]
    assert CreditTransactionType.LLM_USAGE.value not in kinds
    assert kinds.count(CreditTransactionType.REQUEST_FEE.value) == 1


async def test_disabled_billing_meters_nothing(
    billing_run, credit_service, billing_disabled
) -> None:
    """With BILLING_ENABLED=false a run writes no transactions and meets no RPM ceiling."""
    # Arrange
    org_id = billing_run.organization_id

    # Act
    responses = [await billing_run.execute(use_own_key=False, cost_usd=0.01) for _ in range(15)]

    # Assert
    assert all(r.status_code == 200 for r in responses)  # Free RPM is 10; not enforced here
    transactions, total = await credit_service.get_transactions(org_id)
    assert total == 0
