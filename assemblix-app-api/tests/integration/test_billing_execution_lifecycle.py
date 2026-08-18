# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""One credit meter across system-key runs, own-key runs, and a drained balance.

Drives the real production path over HTTP (register -> API key -> credential ->
two published workflows -> execute), so the whole billing gate + deduction path
runs, not just the service layer in isolation.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.billing.credit_service import CreditService
from assemblix_api.database.engine import get_async_engine
from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.database.repositories.credit_transaction_repository import (
    CreditTransactionRepository,
)
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from tests.fixtures.workflows import agent_config, edge, node

# gpt-5.4-mini pricing (assemblix_api/external/llm/models/openai.json): $2.00 / 1M
# output tokens, $0 input tokens used here — lets a test pick an exact USD cost by
# choosing completion_tokens, without depending on real provider pricing.
_OUTPUT_COST_PER_MILLION = Decimal("2.0")


def _arm_cost(mock_llm: Any, cost_usd: float) -> None:
    """Arm the next agent completion to cost exactly ``cost_usd`` (gpt-5.4-mini pricing)."""
    completion_tokens = int(Decimal(str(cost_usd)) * Decimal(1_000_000) / _OUTPUT_COST_PER_MILLION)
    mock_llm.set_response(
        "ok", model="gpt-5.4-mini", prompt_tokens=0, completion_tokens=completion_tokens
    )


def _billing_workflow(*, credential_id: str | None) -> tuple[list[dict], list[dict]]:
    """START -> AGENT (gpt-5.4-mini, given credential) -> END."""
    nodes = [
        node("start", "start", {}),
        node(
            "agent",
            "agent",
            agent_config(model="gpt-5.4-mini", credential_id=credential_id),
        ),
        node("end", "end", {}),
    ]
    edges = [edge("start", "agent"), edge("agent", "end")]
    return nodes, edges


class _CommittedOrganizationRepository:
    """Organization reads/writes on their own committed session against the real engine.

    ``/execute`` runs over ``api_client``, a separate connection that only ever sees
    committed data. The shared ``organization_repository``/``credit_service`` fixtures
    are bound to the rolled-back ``db_session`` transaction, so writes made through them
    would never be visible to ``api_client``'s own connection. This local override
    (same fixture names, shadowing the global ones for this module) commits every write
    immediately and reads through a fresh session, matching how ``billing_run`` itself
    talks to the DB.
    """

    async def reissue_granted_credits(
        self, organization_id: Any, amount: Decimal, *, period_start: Any
    ) -> None:
        async with AsyncSession(get_async_engine()) as session:
            await OrganizationRepository(session).reissue_granted_credits(
                organization_id, amount, period_start=period_start
            )
            await session.commit()

    async def get_by_id(self, organization_id: Any) -> Any:
        async with AsyncSession(get_async_engine()) as session:
            return await OrganizationRepository(session).get_by_id(organization_id)


class _CommittedCreditService:
    """Read-only CreditService view over the real committed engine (see above)."""

    async def get_transactions(self, organization_id: Any) -> tuple[list[dict], int]:
        async with AsyncSession(get_async_engine()) as session:
            service = CreditService(
                OrganizationRepository(session), CreditTransactionRepository(session)
            )
            return await service.get_transactions(organization_id)


@pytest_asyncio.fixture
async def organization_repository() -> Any:
    """Shadow the global (db_session-bound) fixture with a committed-engine one."""
    return _CommittedOrganizationRepository()


@pytest_asyncio.fixture
async def credit_service() -> Any:
    """Shadow the global (db_session-bound) fixture with a committed-engine one."""
    return _CommittedCreditService()


@pytest_asyncio.fixture
async def billing_run(api_client: Any, mock_llm: Any, billing_enabled: Any) -> SimpleNamespace:
    """Registers a PRO-plan org with a system-key workflow and an own-key workflow.

    ``execute(use_own_key, cost_usd)`` arms the mocked LLM call for the given USD
    cost and posts to the matching published workflow's execute endpoint.
    """
    reg = await api_client.post(
        "/api/auth/register", json={"email": "fee-meter@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]
    org_id = reg.json()["organizationId"]

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "fee-meter-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    # Explicit plan — never rely on the default (BUSINESS while billing is disabled).
    async with AsyncSession(get_async_engine()) as session:
        org_repo = OrganizationRepository(session)
        org = await org_repo.get_by_id(org_id)
        await org_repo.update(org, plan="pro")
        await session.commit()

    credential_resp = await api_client.post(
        "/api/credentials/",
        json={
            "type": "openai_token",
            "value": "sk-test-own-key",
            "name": "Own OpenAI",
            "projectId": project_id,
        },
        headers=jwt_headers,
    )
    assert credential_resp.status_code == 201
    credential_id = credential_resp.json()["id"]

    async def _publish(*, own_key: bool) -> str:
        nodes, edges = _billing_workflow(credential_id=credential_id if own_key else None)
        create_resp = await api_client.post(
            "/api/workflows/",
            json={
                "projectId": project_id,
                "name": f"Fee test workflow ({'own' if own_key else 'system'} key)",
                "nodes": nodes,
                "edges": edges,
            },
            headers=jwt_headers,
        )
        assert create_resp.status_code == 201
        workflow_id = create_resp.json()["id"]
        publish_resp = await api_client.post(
            f"/api/workflows/{workflow_id}/publish", headers=jwt_headers
        )
        assert publish_resp.status_code == 200
        return workflow_id

    system_workflow_id = await _publish(own_key=False)
    own_workflow_id = await _publish(own_key=True)

    async def execute(*, use_own_key: bool, cost_usd: float) -> Any:
        _arm_cost(mock_llm, cost_usd)
        workflow_id = own_workflow_id if use_own_key else system_workflow_id
        return await api_client.post(
            f"/api/workflows/{workflow_id}/execute",
            json={"input": {"message": "hi"}},
            headers=key_headers,
        )

    return SimpleNamespace(organization_id=org_id, execute=execute)


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
