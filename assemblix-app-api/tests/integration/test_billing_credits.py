# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Billing test: a FREE org without credits cannot run an LLM workflow.

Drives the real API path: when the org's credit balance is below the minimum, the
execute endpoint's pre-run credit check rejects the run (402) before the agent
(LLM) node executes.
"""

from __future__ import annotations

import uuid

from tests.fixtures.workflows import linear_agent_workflow


async def _set_org_free_with_credits(org_id: str, credits: int) -> None:
    """Force the organization onto the FREE plan with the given credit balance."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from assemblix_api.database.engine import get_async_engine
    from assemblix_api.database.repositories.organization_repository import OrganizationRepository

    async with AsyncSession(get_async_engine()) as session:
        repo = OrganizationRepository(session)
        org = await repo.get_by_id(uuid.UUID(org_id))
        await repo.update(org, plan="free", credits_balance=0 if credits == 0 else credits)
        await session.commit()


async def test_run_fails_without_enough_credits(api_client, mock_llm) -> None:
    """FREE org with 0 credits → POST /execute is rejected with 402."""
    # Arrange — register, force the org onto FREE, then drain its credits to zero.
    mock_llm.set_response("ok")
    reg = await api_client.post(
        "/api/auth/register", json={"email": "broke@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]
    org_id = reg.json()["organizationId"]

    await _set_org_free_with_credits(org_id, 0)

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "exec-key"},
        headers=jwt_headers,
    )
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    nodes, edges = linear_agent_workflow()
    create_resp = await api_client.post(
        "/api/workflows/",
        json={"projectId": project_id, "name": "Billed WF", "nodes": nodes, "edges": edges},
        headers=jwt_headers,
    )
    workflow_id = create_resp.json()["id"]
    await api_client.post(f"/api/workflows/{workflow_id}/publish", headers=jwt_headers)

    # Act — try to run the workflow (which contains an LLM/agent node).
    resp = await api_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input": {"message": "hi"}},
        headers=key_headers,
    )

    # Assert — rejected for insufficient credits, the agent never runs.
    assert resp.status_code == 402
    assert mock_llm.call_count == 0
