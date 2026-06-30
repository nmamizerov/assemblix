# /services/execution_tracer.py

from __future__ import annotations

from uuid import UUID

from assemblix_api.database.models.execution_step import ExecutionStep
from assemblix_api.database.repositories.execution_step_repository import (
    ExecutionStepRepository,
)
from assemblix_api.schemas.execution import ExecutionStepData


class ExecutionTracerService:
    """
    Service for logging execution steps.
    Supports both immediate and batch mode for performance.
    """

    def __init__(self, repository: ExecutionStepRepository):
        self._repository = repository

    async def log_step(self, step_data: ExecutionStepData) -> ExecutionStep:
        """
        Log a single execution step.

        Args:
            step_data: All data for the step

        Returns:
            Created ExecutionStep instance
        """
        step = await self._repository.create(**step_data.model_dump())

        return step

    async def get_last_agent_output(self, execution_id: UUID) -> dict | None:
        """Return output_data of the most recent AGENT step, or None if there were none."""
        last_agent_step = await self._repository.get_last_agent_step(execution_id)

        if last_agent_step and last_agent_step.output_data:
            return last_agent_step.output_data

        return None

    async def has_step(self, execution_id: UUID, step_number: int) -> bool:
        """Check whether an ExecutionStep already exists for the given step_number."""
        return await self._repository.exists_for_step(execution_id, step_number)

    async def get_steps(self, execution_id: UUID) -> list[ExecutionStep]:
        """Return all ExecutionStep records for an execution, ordered by step_number.

        Delegates directly to the repository; the result is passed to
        find_resume_point() in the executor's _preparation_phase when
        execution_checkpointing_enabled is True.

        Args:
            execution_id: ID of the execution whose steps to fetch.

        Returns:
            List of ExecutionStep instances ordered by step_number ascending.
        """
        return await self._repository.get_steps(execution_id)

    async def get_node_output(self, execution_id: UUID, node_id: str) -> dict | None:
        """Return output_data of a specific node, or None if it did not execute."""
        step = await self._repository.get_step_by_node_id(execution_id, node_id)

        if step and step.output_data:
            return step.output_data

        return None
