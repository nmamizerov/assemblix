"""Prod-like queue test: workflows launched via the API are processed by an Arq
worker limited to one concurrent job.

Flow (everything via real API requests, queue mode on):
* register → API key → create workflow → publish;
* POST /execute twice → both return immediately with an execution id (queued);
* a real in-process Arq worker (``max_jobs=1``) runs them one at a time: the first
  is blocked on the mocked LLM call → it is RUNNING while the second stays QUEUED;
* release the first → it completes, the worker picks up the second, both COMPLETED.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any

from assemblix_api.database.engine import get_async_engine
from assemblix_api.enums import ExecutionStatus
from tests.fixtures.workflows import linear_agent_workflow

_COMPLETION = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4o",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


class _Resp:
    def model_dump(self, *args: Any, **kwargs: Any) -> dict:
        return _COMPLETION


async def _status(execution_id: str) -> ExecutionStatus:
    """Read an execution's status in a fresh session (sees committed worker writes)."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from assemblix_api.database.repositories.execution_repository import ExecutionRepository

    async with AsyncSession(get_async_engine()) as session:
        row = await ExecutionRepository(session).get_by_id(uuid.UUID(execution_id))
        return row.status


async def _setup_published_workflow(queue_client) -> tuple[dict, str]:
    """Register, mint an API key, create + publish a workflow. Return (key_headers, workflow_id)."""
    reg = await queue_client.post(
        "/api/auth/register", json={"email": "queue@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]

    key_resp = await queue_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "queue-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    nodes, edges = linear_agent_workflow()
    create_resp = await queue_client.post(
        "/api/workflows/",
        json={"projectId": project_id, "name": "Queue WF", "nodes": nodes, "edges": edges},
        headers=jwt_headers,
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    publish_resp = await queue_client.post(
        f"/api/workflows/{workflow_id}/publish", headers=jwt_headers
    )
    assert publish_resp.status_code == 200
    return key_headers, workflow_id


async def test_queue_runs_one_workflow_at_a_time(queue_client, redis_url, mocker) -> None:
    """Two API-launched runs: second waits QUEUED until the first finishes."""
    # Arrange — block the first LLM call so its job stays RUNNING; others pass through.
    first_started = asyncio.Event()
    release = asyncio.Event()
    calls = {"n": 0}

    async def _acompletion(**kwargs: Any) -> _Resp:
        calls["n"] += 1
        if calls["n"] == 1:
            first_started.set()
            await release.wait()
        return _Resp()

    mocker.patch(
        "assemblix_api.external.llm.litellm_model.litellm.acompletion", side_effect=_acompletion
    )

    key_headers, workflow_id = await _setup_published_workflow(queue_client)

    # Act — launch the workflow twice via the API. task=True keeps the queue path
    # fire-and-forget (returns immediately); task=False would block on the
    # completion signal (covered by test_queue_task_false_waits_for_result).
    async def _launch() -> str:
        resp = await queue_client.post(
            f"/api/workflows/{workflow_id}/execute",
            json={"input": {"message": "hi"}, "task": True},
            headers=key_headers,
        )
        assert resp.status_code == 200
        return resp.json()["executionId"]

    id1 = await _launch()
    id2 = await _launch()

    # Both rows are committed and QUEUED before any worker runs.
    assert await _status(id1) == ExecutionStatus.QUEUED
    assert await _status(id2) == ExecutionStatus.QUEUED

    # Start a real in-process Arq worker that runs ONE job at a time.
    from arq.connections import RedisSettings
    from arq.worker import Worker

    from assemblix_api.queue.jobs import run_workflow_job

    worker = Worker(
        functions=[run_workflow_job],
        redis_settings=RedisSettings.from_dsn(redis_url),
        max_jobs=1,
        poll_delay=0.05,
        handle_signals=False,
    )
    worker_task = asyncio.create_task(worker.async_run())

    try:
        # Wait until one job has entered the (blocked) LLM call.
        await asyncio.wait_for(first_started.wait(), timeout=20.0)

        # Assert — exactly one RUNNING, one QUEUED (worker honours max_jobs=1).
        running = [i for i in (id1, id2) if await _status(i) == ExecutionStatus.RUNNING]
        queued = [i for i in (id1, id2) if await _status(i) == ExecutionStatus.QUEUED]
        assert len(running) == 1
        assert len(queued) == 1

        # Release the first job; the worker then picks up the second.
        release.set()

        async def _both_completed() -> None:
            while not (
                await _status(id1) == ExecutionStatus.COMPLETED
                and await _status(id2) == ExecutionStatus.COMPLETED
            ):
                await asyncio.sleep(0.05)

        # Assert — both runs complete once the queue drains.
        await asyncio.wait_for(_both_completed(), timeout=30.0)
    finally:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
        await worker.close()


async def test_queue_task_false_waits_for_result(queue_client, redis_url, mocker) -> None:
    """task=False in queue mode blocks until the worker finishes and returns the result."""
    # Arrange — LLM passes through immediately; a worker drains the queue.
    mocker.patch(
        "assemblix_api.external.llm.litellm_model.litellm.acompletion",
        side_effect=lambda **_: _Resp(),
    )

    key_headers, workflow_id = await _setup_published_workflow(queue_client)

    from arq.connections import RedisSettings
    from arq.worker import Worker

    from assemblix_api.queue.jobs import run_workflow_job

    worker = Worker(
        functions=[run_workflow_job],
        redis_settings=RedisSettings.from_dsn(redis_url),
        max_jobs=1,
        poll_delay=0.05,
        handle_signals=False,
    )
    worker_task = asyncio.create_task(worker.async_run())

    try:
        # Act — task omitted (defaults to False): the request waits for completion.
        resp = await asyncio.wait_for(
            queue_client.post(
                f"/api/workflows/{workflow_id}/execute",
                json={"input": {"message": "hi"}},
                headers=key_headers,
            ),
            timeout=30.0,
        )

        # Assert — the synchronous response carries the completed result, not just an id.
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        execution_id = body["executionId"]
        assert await _status(execution_id) == ExecutionStatus.COMPLETED
    finally:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
        await worker.close()
