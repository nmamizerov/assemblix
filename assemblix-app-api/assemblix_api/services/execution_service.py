"""Execution service - business logic for executions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from assemblix_api.database.models.user import User
    from assemblix_api.services.project_service import ProjectService

from assemblix_api.database.models.execution import Execution
from assemblix_api.database.repositories.execution_repository import ExecutionRepository
from assemblix_api.dto.requests.execution import ExecutionFilters
from assemblix_api.dto.responses.chat_session import ChatSessionBaseResponse
from assemblix_api.dto.responses.execution import (
    ExecutionDetailInfoResponse,
    ExecutionErrorResponse,
    ExecutionInfoResponse,
    ExecutionMetadata,
    ExecutionResponse,
    ExecutionStepResponse,
    InFlightExecutionResponse,
    TaskExecutionResponse,
)
from assemblix_api.dto.responses.workflow import WorkflowBaseResponse, WorkflowResponse
from assemblix_api.enums import ExecutionErrorType, ExecutionStatus
from assemblix_api.services.base_service import BaseService


class ExecutionService(BaseService[Execution, ExecutionRepository]):
    def __init__(self, repository: ExecutionRepository, project_service: ProjectService):
        super().__init__(repository, entity_name="Execution")
        self._project_service = project_service

    async def create_execution(
        self,
        workflow_id: UUID,
        token_id: UUID | None,
        initial_state: dict,
        *,
        chat_session_id: UUID | None = None,
        client_session_id: UUID | None = None,
        input_data: dict | None = None,
        is_debug: bool = False,
    ) -> Execution:
        return await self.create(
            workflow_id=workflow_id,
            token_id=token_id,
            chat_session_id=chat_session_id,
            client_session_id=client_session_id,
            initial_state=initial_state,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(),
            is_debug=is_debug,
            meta_data={"input_data": input_data or {}},
        )

    async def create_queued(
        self,
        workflow_id: UUID,
        token_id: UUID | None,
        initial_state: dict,
        *,
        chat_session_id: UUID | None = None,
        client_session_id: UUID | None = None,
        input_data: dict | None = None,
        is_debug: bool = False,
    ) -> Execution:
        """
        Pre-create an execution row with status QUEUED before pushing to the job queue.

        Called by enqueue_execution so the caller gets an execution_id immediately,
        before the worker picks up the job. The worker must call mark_running() when
        it starts processing the job.

        Args:
            workflow_id: ID of the workflow to execute
            token_id: API key ID (or None for debug mode)
            initial_state: Initial workflow state
            chat_session_id: Chat session ID (for stateful workflows)
            client_session_id: Client session ID (for cross-workflow state)
            input_data: Input data saved in metadata
            is_debug: Debug flag for SSE streaming

        Returns:
            Created execution with status QUEUED and no started_at
        """
        return await self.create(
            workflow_id=workflow_id,
            token_id=token_id,
            chat_session_id=chat_session_id,
            client_session_id=client_session_id,
            initial_state=initial_state,
            status=ExecutionStatus.QUEUED,
            started_at=None,
            is_debug=is_debug,
            meta_data={"input_data": input_data or {}},
        )

    async def mark_running(self, execution_id: UUID) -> Execution:
        """
        Transition a pre-created (QUEUED) execution to RUNNING status.

        Called by the worker when it picks up the execution from the queue.
        Sets started_at only if it was not already set (idempotent for retries).

        Args:
            execution_id: ID of the execution to transition

        Returns:
            Updated execution with status=RUNNING
        """
        execution = await self.get_by_id(execution_id)
        updates: dict = {"status": ExecutionStatus.RUNNING}
        if execution.started_at is None:
            updates["started_at"] = datetime.now()
        return await self._repository.update(execution, **updates)

    async def update_execution_status(
        self,
        execution_id: UUID,
        status: ExecutionStatus,
        *,
        final_state: dict | None = None,
        output: dict | None = None,
        final_project_state: dict | None = None,
        is_session_closed: bool = False,
        error_message: str | None = None,
        error_type: ExecutionErrorType | None = None,
        failed_node_id: str | None = None,
        total_credits: Decimal = Decimal("0"),
        own_key_cost_usd: Decimal | None = None,
        steps_count: int = 0,
    ) -> Execution:
        execution = await self.get_by_id(execution_id)

        # Calculate duration
        completed_at = datetime.now()
        assert execution.started_at is not None  # set when the execution leaves QUEUED
        duration_ms = int((completed_at - execution.started_at).total_seconds() * 1000)

        meta_data: dict = {}
        if final_project_state is not None:
            meta_data["final_project_state"] = final_project_state
        if is_session_closed:
            meta_data["is_session_closed"] = is_session_closed

        return await self.update(
            execution_id,
            status=status,
            final_state=final_state,
            output=output,
            completed_at=completed_at,
            duration_ms=duration_ms,
            error_message=error_message,
            error_type=error_type,
            failed_node_id=failed_node_id,
            total_credits=total_credits,
            own_key_cost_usd=own_key_cost_usd,
            steps_count=steps_count,
            **({"meta_data": meta_data} if meta_data else {}),
        )

    async def get_execution(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> Execution:
        execution = await self.get_by_id(execution_id)

        if execution.workflow.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для доступа к этому execution",
            )

        return execution

    async def get_execution_detail(
        self,
        execution_id: UUID,
        current_user: User,
        scoped_project_id: UUID | None = None,
    ) -> ExecutionDetailInfoResponse:
        """
        Get full execution info with access control.

        The project is derived from the execution (via workflow); user access is
        verified through organization membership, so the X-Project-Id header is
        not required for this endpoint. ``scoped_project_id`` additionally hard-scopes
        a project-bound API key to its own project.
        """
        execution = await self._repository.get_with_details(execution_id)

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution с ID {execution_id} не найден",
            )

        await self._project_service.verify_user_project_access(
            current_user, execution.workflow.project_id
        )

        if scoped_project_id is not None and scoped_project_id != execution.workflow.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API-ключ не имеет доступа к этому проекту",
            )

        steps = [
            ExecutionStepResponse.model_validate(step, from_attributes=True)
            for step in execution.steps
        ]

        workflow = WorkflowResponse.model_validate(execution.workflow, from_attributes=True)

        chat_session = None
        if execution.chat_session:
            chat_session = ChatSessionBaseResponse.model_validate(
                execution.chat_session, from_attributes=True
            )

        execution_dict = {k: v for k, v in execution.__dict__.items() if not k.startswith("_")}
        execution_dict.update(
            {
                "steps": steps,
                "workflow": workflow,
                "chat_session": chat_session,
            }
        )

        return ExecutionDetailInfoResponse(**execution_dict)

    async def get_executions_list(
        self,
        project_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
        filters: ExecutionFilters | None = None,
    ) -> tuple[list[ExecutionInfoResponse], int]:
        executions, total = await self._repository.get_executions_list(
            project_id=project_id,
            offset=offset,
            limit=limit,
            filters=filters,
        )

        execution_responses = []
        for execution in executions:
            workflow = WorkflowBaseResponse.model_validate(execution.workflow, from_attributes=True)

            chat_session = None
            if execution.chat_session:
                chat_session = ChatSessionBaseResponse.model_validate(
                    execution.chat_session, from_attributes=True
                )

            execution_dict = {k: v for k, v in execution.__dict__.items() if not k.startswith("_")}
            execution_dict.update(
                {
                    "workflow": workflow,
                    "chat_session": chat_session,
                }
            )

            execution_responses.append(ExecutionInfoResponse(**execution_dict))

        return execution_responses, total

    async def get_in_flight(self, project_id: UUID) -> list[InFlightExecutionResponse]:
        """
        Return in-flight (QUEUED or RUNNING) executions for a project.

        Delegates project-scoped status filtering to the repository; converts
        results to InFlightExecutionResponse DTOs.

        Args:
            project_id: The caller's project ID (used to scope the query).

        Returns:
            List of InFlightExecutionResponse with id/workflow_id/status/started_at/steps_count.
        """
        rows = await self._repository.get_in_flight(project_id)
        return [
            InFlightExecutionResponse(
                id=row.id,
                workflow_id=row.workflow_id,
                status=row.status,
                # For QUEUED rows started_at is None; fall back to created_at (always set
                # via TimestampMixin) so the response carries a usable timestamp.
                started_at=row.started_at or row.created_at,
                steps_count=row.steps_count,
            )
            for row in rows
        ]

    async def get_task_result(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> TaskExecutionResponse | ExecutionResponse | ExecutionErrorResponse:
        """
        Get the result of a task-mode workflow execution (used for polling).

        Returns:
            TaskExecutionResponse - still running (RUNNING/QUEUED)
            ExecutionResponse - completed successfully (COMPLETED)
            ExecutionErrorResponse - finished with an error (FAILED/ERROR)
        """
        execution = await self._repository.get_with_details(execution_id)

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution с ID {execution_id} не найден",
            )

        if execution.workflow.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для доступа к этому execution",
            )

        # Still in progress: QUEUED (enqueued, not yet picked up) is treated like RUNNING
        # so polling does not falsely report a freshly-enqueued row as completed.
        if execution.status in (ExecutionStatus.RUNNING, ExecutionStatus.QUEUED):
            return TaskExecutionResponse(execution_id=execution.id, status="running")

        if execution.status in (ExecutionStatus.FAILED, ExecutionStatus.ERROR):
            return ExecutionErrorResponse(
                execution_id=execution.id,
                status="failed",
                error=execution.error_message or "Unknown error",
                error_type=(execution.error_type.value if execution.error_type else "runtime"),
                failed_node_id=execution.failed_node_id,
                partial_state=execution.final_state or {},
                partial_project_state=(
                    execution.meta_data.get("final_project_state", {})
                    if execution.meta_data
                    else {}
                ),
            )

        project_state = {}
        is_session_closed = False
        if execution.meta_data:
            project_state = execution.meta_data.get("final_project_state", {})
            is_session_closed = execution.meta_data.get("is_session_closed", False)

        return ExecutionResponse(
            execution_id=execution.id,
            session_id=execution.chat_session_id,
            output=execution.output or {},
            state=execution.final_state or {},
            status="completed",
            project_state=project_state,
            metadata=ExecutionMetadata(
                total_steps=execution.steps_count,
                duration_ms=execution.duration_ms,
                credits_used=float(execution.total_credits),
                own_key_cost_usd=(
                    float(execution.own_key_cost_usd)
                    if execution.own_key_cost_usd is not None
                    else None
                ),
            ),
            is_session_closed=is_session_closed,
        )
