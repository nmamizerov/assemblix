# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Shared fixture machinery for the billing-lifecycle tests in this directory.

Scope-local (this directory only, per the pattern in ``tests/integration/queue/
conftest.py``): the ``organization_repository``/``credit_service`` overrides here
commit to the real engine (see ``_CommittedOrganizationRepository`` below) rather
than the rolled-back ``db_session`` the rest of the suite uses, so they must not
leak into sibling billing test files that rely on the default, transactional
fixtures.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.billing.credit_service import CreditService
from assemblix_api.database.engine import get_async_engine
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
    (same fixture names, shadowing the global ones for this directory) commits every
    write immediately and reads through a fresh session, matching how ``billing_run``
    itself talks to the DB.
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
    """Registers a Free-plan org with a system-key workflow and an own-key workflow.

    ``execute(use_own_key, cost_usd)`` arms the mocked LLM call for the given USD
    cost and posts to the matching published workflow's execute endpoint. Free is
    the explicit plan (RPM 10) rather than the default so callers can exercise the
    RPM ceiling deliberately.
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
        await org_repo.update(org, plan="free")
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

    result = SimpleNamespace(
        organization_id=org_id,
        project_id=project_id,
        jwt_headers=jwt_headers,
    )

    async def execute(*, use_own_key: bool, cost_usd: float) -> Any:
        _arm_cost(mock_llm, cost_usd)
        workflow_id = own_workflow_id if use_own_key else system_workflow_id
        return await api_client.post(
            f"/api/workflows/{workflow_id}/execute",
            json={"input": {"message": "hi"}},
            headers=key_headers,
        )

    result.execute = execute
    return result
