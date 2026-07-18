"""Regression: parallel fork branches share one AsyncSession.

A workflow run uses a single AsyncSession for every branch (see build_executor).
On the parallel engine, fork branches execute as concurrent asyncio tasks, so two
branches can `await` the DB at the same instant. A bare AsyncSession forbids that
("concurrent operations are not permitted"). SerializedAsyncSession serializes only
the DB touch points with a per-task reentrant lock, so concurrent branches succeed
while the expensive awaits (LLM/HTTP) between DB calls still overlap.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.engine import SerializedAsyncSession


async def _overlapping_queries(session: AsyncSession, n: int = 6) -> list[int]:
    """Fire n queries concurrently; pg_sleep widens each await window so they overlap."""

    async def one(i: int) -> int:
        result = await session.execute(
            text("SELECT CAST(:i AS INTEGER) AS i, pg_sleep(0.05)"), {"i": i}
        )
        return int(result.scalar())

    return await asyncio.gather(*(one(i) for i in range(n)))


async def test_plain_session_races_on_concurrent_ops(committed_db) -> None:
    """Control: a bare AsyncSession raises when two branches await the DB at once."""
    # Arrange
    session = AsyncSession(committed_db)

    # Act / Assert — the shared-session hazard reproduces on the stock session. The guard
    # surfaces as one of SQLAlchemy's concurrency errors ("concurrent operations are not
    # permitted" in prod; an IllegalStateChangeState mid-provision here) — match the family.
    with pytest.raises(Exception, match="concurrent operations|already in progress|can't be called here"):
        await _overlapping_queries(session)

    # The race leaves the bare session mid-provision; closing it is best-effort teardown.
    with contextlib.suppress(Exception):
        await session.close()


async def test_serialized_session_allows_concurrent_branches(committed_db) -> None:
    """SerializedAsyncSession serializes DB touches so concurrent branches all succeed."""
    # Arrange
    session = SerializedAsyncSession(committed_db)

    # Act
    results = await _overlapping_queries(session)

    # Assert — every branch completed, none lost to the concurrency guard.
    assert sorted(results) == [0, 1, 2, 3, 4, 5]

    await session.close()


async def test_serialized_session_reentrant_scalar(committed_db) -> None:
    """`scalar` calls `execute` internally; the per-task lock must reenter, not deadlock."""
    # Arrange
    session = SerializedAsyncSession(committed_db)

    # Act — would hang forever if the lock were non-reentrant within one task.
    value = await asyncio.wait_for(session.scalar(text("SELECT 42")), timeout=5)

    # Assert
    assert value == 42

    await session.close()
