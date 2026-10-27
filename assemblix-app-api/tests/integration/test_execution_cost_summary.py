"""GET /api/executions/cost-summary — runs and spend for the key's project since a date,
with a per-day (UTC) breakdown."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from assemblix_api.database.models.execution import Execution
from assemblix_api.database.models.execution_step import ExecutionStep
from assemblix_api.database.models.workflow import Workflow
from assemblix_api.enums import ExecutionStatus, StepStatus


async def _workflow(db_session, project_id) -> Workflow:
    wf = Workflow(project_id=project_id, slug=str(uuid4()), name="WF")
    db_session.add(wf)
    await db_session.flush()
    return wf


async def _run(
    db_session,
    workflow_id,
    created_at: datetime,
    *,
    credits: str = "0",
    usd: str | None = None,
    tokens: list[int] | None = None,
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    is_debug: bool = False,
) -> None:
    execution = Execution(
        workflow_id=workflow_id,
        initial_state={},
        status=status,
        is_debug=is_debug,
        created_at=created_at,
        started_at=created_at,
        total_credits=Decimal(credits),
        own_key_cost_usd=Decimal(usd) if usd is not None else None,
    )
    db_session.add(execution)
    await db_session.flush()
    for i, used in enumerate(tokens or []):
        db_session.add(
            ExecutionStep(
                execution_id=execution.id,
                step_number=i,
                node_id=f"n{i}",
                node_type="agent",
                status=StepStatus.COMPLETED,
                started_at=created_at,
                tokens_used=used,
            )
        )
    await db_session.flush()


async def test_cost_summary_totals_and_daily_breakdown(client, api_key, db_session) -> None:
    # Arrange: two runs on Oct 1 (one failed), one on Oct 3.
    wf = await _workflow(db_session, api_key.record.project_id)
    await _run(
        db_session, wf.id, datetime(2026, 10, 1, 9), credits="1.5", usd="0.01", tokens=[100, 50]
    )
    await _run(
        db_session,
        wf.id,
        datetime(2026, 10, 1, 23, 59),
        credits="0.5",
        status=ExecutionStatus.FAILED,
    )
    await _run(db_session, wf.id, datetime(2026, 10, 3, 12), credits="2", usd="0.04", tokens=[300])

    # Act
    resp = await client.get(
        "/api/executions/cost-summary", params={"since": "2026-10-01"}, headers=api_key.headers
    )

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["since"] == "2026-10-01"
    assert body["totalRuns"] == 3
    assert body["failedRuns"] == 1
    assert body["totalCredits"] == 4.0
    assert body["ownKeyCostUsd"] == 0.05
    assert body["tokensUsed"] == 450
    assert body["days"] == [
        {
            "date": "2026-10-01",
            "runs": 2,
            "failedRuns": 1,
            "credits": 2.0,
            "ownKeyCostUsd": 0.01,
            "tokensUsed": 150,
        },
        {
            "date": "2026-10-03",
            "runs": 1,
            "failedRuns": 0,
            "credits": 2.0,
            "ownKeyCostUsd": 0.04,
            "tokensUsed": 300,
        },
    ]


async def test_cost_summary_respects_since_and_until(client, api_key, db_session) -> None:
    # Arrange: one run on each side of the window and one inside it.
    wf = await _workflow(db_session, api_key.record.project_id)
    await _run(db_session, wf.id, datetime(2026, 9, 30, 23, 59), credits="1")
    await _run(db_session, wf.id, datetime(2026, 10, 2, 0, 0), credits="2")
    await _run(db_session, wf.id, datetime(2026, 10, 3, 0, 0), credits="4")

    # Act: until is inclusive of the whole day.
    resp = await client.get(
        "/api/executions/cost-summary",
        params={"since": "2026-10-01", "until": "2026-10-02"},
        headers=api_key.headers,
    )

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalRuns"] == 1
    assert body["totalCredits"] == 2.0
    assert [d["date"] for d in body["days"]] == ["2026-10-02"]


async def test_cost_summary_excludes_debug_and_foreign_projects(
    client, api_key, auth_headers, db_session
) -> None:
    # Arrange: a debug run in the key's project and a run in another project.
    wf = await _workflow(db_session, api_key.record.project_id)
    await _run(db_session, wf.id, datetime(2026, 10, 1, 10), credits="1", is_debug=True)
    proj = await client.post("/api/projects/", json={"name": "Other"}, headers=auth_headers)
    other_wf = await _workflow(db_session, proj.json()["id"])
    await _run(db_session, other_wf.id, datetime(2026, 10, 1, 10), credits="7")

    # Act
    resp = await client.get(
        "/api/executions/cost-summary", params={"since": "2026-10-01"}, headers=api_key.headers
    )

    # Assert: nothing counted, and the empty shape is still well-formed.
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalRuns"] == 0
    assert body["totalCredits"] == 0.0
    assert body["ownKeyCostUsd"] == 0.0
    assert body["tokensUsed"] == 0
    assert body["days"] == []


async def test_cost_summary_requires_since(client, api_key) -> None:
    # Act
    resp = await client.get("/api/executions/cost-summary", headers=api_key.headers)
    # Assert
    assert resp.status_code == 422
