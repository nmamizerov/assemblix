"""Execution step repository - database operations for execution_steps."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.execution_step import ExecutionStep
from assemblix_api.database.repositories.base_repository import BaseRepository
from assemblix_api.enums import NodeType


class ExecutionStepRepository(BaseRepository[ExecutionStep]):
    """Repository for the execution_steps table."""

    def __init__(self, session: AsyncSession):
        super().__init__(ExecutionStep, session)

    async def get_last_agent_step(self, execution_id: UUID) -> ExecutionStep | None:
        """Get the last executed AGENT-type step for an execution."""
        stmt = (
            select(ExecutionStep)
            .where(ExecutionStep.execution_id == execution_id)
            .where(ExecutionStep.node_type == NodeType.AGENT)
            .order_by(ExecutionStep.step_number.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_step_by_node_id(self, execution_id: UUID, node_id: str) -> ExecutionStep | None:
        """Get the last executed step for a specific node."""
        stmt = (
            select(ExecutionStep)
            .where(ExecutionStep.execution_id == execution_id)
            .where(ExecutionStep.node_id == node_id)
            .order_by(ExecutionStep.step_number.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_for_step(self, execution_id: UUID, step_number: int) -> bool:
        """Check whether a step record exists for the given execution_id and step_number."""
        stmt = (
            select(ExecutionStep.id)
            .where(ExecutionStep.execution_id == execution_id)
            .where(ExecutionStep.step_number == step_number)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_steps(self, execution_id: UUID) -> list[ExecutionStep]:
        """Return all steps for an execution ordered by step_number ascending.

        Used by the resume logic to derive the crash-resume position from
        persisted ExecutionStep records.

        Args:
            execution_id: ID of the execution whose steps to fetch.

        Returns:
            All ExecutionStep rows for that execution, sorted by step_number.
        """
        stmt = (
            select(ExecutionStep)
            .where(ExecutionStep.execution_id == execution_id)
            .order_by(ExecutionStep.step_number)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
