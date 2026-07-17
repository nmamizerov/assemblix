"""
Execution REST API endpoints
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.api.rest._scope import resolve_project_id
from assemblix_api.billing.service import BillingService
from assemblix_api.core.auth_context import AuthContext
from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.user import User
from assemblix_api.database.models.workflow import Workflow
from assemblix_api.dependencies import (
    get_arq_pool,
    get_auth_context,
    get_billing_service,
    get_chat_service,
    get_client_session_service,
    get_current_user,
    get_db_session,
    get_debug_event_manager,
    get_execution_service,
    get_project_id_from_token,
    get_project_id_from_token_with_access_check,
    get_project_service,
    get_token_id_from_request,
    get_token_id_optional,
    get_workflow_service,
    run_workflow_isolated,
)
from assemblix_api.dto.base import PaginatedResponse
from assemblix_api.dto.requests.execution import (
    ExecuteWorkflowRequest,
    ExecutionFilters,
)
from assemblix_api.dto.responses.execution import (
    ExecutionDetailInfoResponse,
    ExecutionErrorResponse,
    ExecutionInfoResponse,
    ExecutionMetadata,
    ExecutionResponse,
    InFlightExecutionResponse,
    TaskExecutionResponse,
)
from assemblix_api.enums import ExecutionStatus
from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.execution.voice_gate import (
    ensure_audio_run_is_synchronous,
    load_audio_into_input_data,
)
from assemblix_api.queue.enqueue import enqueue_execution
from assemblix_api.schemas.execution import AudioInput
from assemblix_api.services.chat_service import ChatService
from assemblix_api.services.client_session_service import ClientSessionService
from assemblix_api.services.execution_service import ExecutionService
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.workflow_service import WorkflowService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/workflows", tags=["Executions"])
execution_detail_router = APIRouter(prefix="/executions", tags=["Executions"])


async def _await_queued_result(
    *,
    execution_service: ExecutionService,
    session: AsyncSession,
    execution_id: UUID,
    project_id: UUID,
    timeout: float,
) -> ExecutionResponse | ExecutionErrorResponse | TaskExecutionResponse:
    """Wait for a queued execution to finish, preserving the sync /execute contract.

    Subscribes to the execution's Redis completion channel first, then checks the
    DB once (covering a worker that finished before we subscribed), then blocks on
    the signal up to *timeout*.  Each DB read is followed by a rollback so the
    request never holds a pooled DB connection while idling on Redis and so the
    next read returns the worker's freshly committed state.  Falls back to async
    mode (just the execution_id) on timeout.
    """
    from assemblix_api.core.redis_client import get_redis
    from assemblix_api.queue.completion import (
        close_completion_subscription,
        open_completion_subscription,
        wait_for_signal,
    )

    redis = await get_redis()
    pubsub = await open_completion_subscription(redis, execution_id)
    try:
        # Initial read: the worker may have finished before we subscribed.
        result = await execution_service.get_task_result(execution_id, project_id)
        await session.rollback()
        if not isinstance(result, TaskExecutionResponse):
            return result

        if not await wait_for_signal(pubsub, timeout):
            # Still running past the timeout — switch to async mode.
            return TaskExecutionResponse(execution_id=execution_id)

        result = await execution_service.get_task_result(execution_id, project_id)
        await session.rollback()
        if isinstance(result, TaskExecutionResponse):
            # Signalled but not yet terminal (rare) — let the client poll.
            return TaskExecutionResponse(execution_id=execution_id)
        return result
    finally:
        await close_completion_subscription(pubsub, execution_id)


async def _load_and_authorize(
    workflow_id: UUID,
    *,
    project_id_from_token: UUID,
    session_id: UUID | None,
    resolve_published: bool,
    workflow_service: WorkflowService,
    chat_service: ChatService,
    billing_service: BillingService,
    project_service: ProjectService,
    current_user: User | None = None,
) -> Workflow:
    """Shared entry checks for every execute variant (text and audio).

    Loads the workflow (404), verifies the caller's token owns it (403; admins
    bypass in debug), validates an optional existing session (400), applies the
    billing/RPM check, and — for the sync path — resolves the latest published
    version. Returns the workflow that should actually run.
    """
    try:
        workflow = await workflow_service.get_by_id(workflow_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow с ID {workflow_id} не найден",
        ) from e

    # Checked for all workflows (published and draft) to prevent unauthorized
    # access to a workflow via API keys belonging to other projects. Admins may
    # run any workflow in debug mode.
    is_admin = bool(current_user and current_user.is_admin)
    if not is_admin and workflow.project_id != project_id_from_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Токен не принадлежит проекту workflow",
        )

    if session_id:
        try:
            await chat_service.get_by_id(session_id)
        except HTTPException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chat session с ID {session_id} не найдена",
            ) from e

    # Check RPM limit and credit balance (FREE plans)
    project = await project_service.get_by_id(workflow.project_id)
    if project:
        await billing_service.check_and_deduct_credits(project.organization_id)

    # If this is a draft, resolve the latest published version (required).
    # Debug mode runs exactly the workflow given (draft); no version is resolved,
    # since the developer is testing this specific workflow.
    if resolve_published and workflow.published_for_workflow_id is None:
        published_workflow = await workflow_service.get_latest_published(workflow_id)
        if not published_workflow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workflow {workflow_id} не имеет опубликованных версий. Опубликуйте workflow перед выполнением.",
            )
        workflow = published_workflow

    return workflow


def _build_input_data(request: ExecuteWorkflowRequest, *, is_debug: bool) -> dict:
    """Assemble the executor's ``input_data`` bag from the request (shared)."""
    input_data = request.input.copy()

    if is_debug:
        input_data["is_debug"] = True
    if request.stream:
        input_data["stream"] = True

    if request.create_session:
        input_data["create_session"] = True
    if request.session_name is not None:
        input_data["session_name"] = request.session_name
    if request.state is not None:
        input_data["state"] = request.state
    if request.project_state is not None:
        input_data["project_state"] = request.project_state
    if request.client_id:
        input_data["client_id"] = request.client_id
    if request.metadata:
        input_data["metadata"] = request.metadata

    input_data.setdefault("input_type", "text")

    return input_data


async def _dispatch_sync(
    workflow: Workflow,
    input_data: dict,
    *,
    request: ExecuteWorkflowRequest,
    project_id: UUID,
    token_id: UUID,
    execution_service: ExecutionService,
    session: AsyncSession,
    audio_input: AudioInput | None = None,
) -> ExecutionResponse | ExecutionErrorResponse | TaskExecutionResponse:
    """Run a workflow synchronously and shape the response (shared by /execute
    and /execute/audio).

    With task=False (default) the behavior depends on duration:
    - Workflow finished within TASK_TIMEOUT_SECONDS → 200 ExecutionResponse
    - Workflow not finished → TaskExecutionResponse (continues in background)
    """
    # Queue branch: when the Arq queue is enabled, enqueue the job onto the Arq
    # worker. With task=True we return immediately (fire-and-forget). With
    # task=False we preserve the synchronous contract of the in-process path:
    # wait for the worker to finish (via a Redis completion signal) up to
    # TASK_TIMEOUT_SECONDS, then return the result — falling back to async mode
    # (just the execution_id) on timeout.
    settings = get_settings()
    if settings.execution_queue_enabled:
        try:
            ensure_audio_run_is_synchronous(input_data=input_data, queued=True)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        arq_redis = await get_arq_pool()
        execution_id = await enqueue_execution(
            execution_service,
            arq_redis,
            workflow_id=workflow.id,
            input_data=input_data,
            token_id=token_id,
            chat_session_id=request.session_id,
        )
        # Commit so the QUEUED row is visible to the worker (separate session)
        # and the in-memory row is expired — later reads in this request return
        # the worker's committed terminal state instead of a stale QUEUED copy.
        await session.commit()

        if request.task:
            return TaskExecutionResponse(execution_id=execution_id)

        return await _await_queued_result(
            execution_service=execution_service,
            session=session,
            execution_id=execution_id,
            project_id=project_id,
            timeout=float(settings.task_timeout_seconds),
        )

    # Run the workflow in an isolated session with futures for feedback
    loop = asyncio.get_event_loop()
    execution_id_future: asyncio.Future = loop.create_future()
    result_future: asyncio.Future = loop.create_future()

    from assemblix_api.execution.background_tasks import background_task_registry

    task = asyncio.create_task(
        run_workflow_isolated(
            workflow_id=workflow.id,
            input_data=input_data,
            token_id=token_id,
            chat_session_id=request.session_id,
            execution_id_future=execution_id_future,
            result_future=result_future,
            audio_input=audio_input,
        )
    )
    background_task_registry.track(task)

    # Wait for execution_id (needed for both task=True and task=False)
    try:
        execution_id = await asyncio.wait_for(
            asyncio.shield(execution_id_future),
            timeout=30.0,
        )
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Workflow не удалось запустить в течение 30 секунд",
        ) from e

    if request.task:
        return TaskExecutionResponse(execution_id=execution_id)

    # task=False — wait for the result with a TASK_TIMEOUT_SECONDS timeout
    try:
        result = await asyncio.wait_for(
            asyncio.shield(result_future),
            timeout=float(settings.task_timeout_seconds),
        )
    except TimeoutError:
        # Workflow runs longer than the timeout — switch to async mode
        return TaskExecutionResponse(execution_id=execution_id)

    if result.status == "failed":
        return ExecutionErrorResponse(
            execution_id=result.execution_id,
            status="failed",
            error=result.metadata.error_message or "Unknown error",
            error_type=result.metadata.error_type or "runtime",
            failed_node_id=result.metadata.failed_node_id,
            partial_state=result.final_state,
            partial_project_state=result.final_project_state,
        )

    return ExecutionResponse(
        execution_id=result.execution_id,
        session_id=result.session_id,
        output=result.output,
        state=result.final_state,
        status=result.status,
        project_state=result.final_project_state,
        metadata=ExecutionMetadata(
            total_steps=result.metadata.steps_count,
            duration_ms=result.metadata.duration_ms,
            credits_used=result.metadata.total_credits,
            own_key_cost_usd=result.metadata.own_key_cost_usd,
        ),
        is_session_closed=result.is_session_closed,
    )


def _dispatch_debug_stream(
    workflow: Workflow,
    input_data: dict,
    *,
    session_id: UUID | None,
    token_id: UUID | None,
    debug_event_manager: DebugEventManager,
    audio_input: AudioInput | None = None,
) -> StreamingResponse:
    """Start a debug run and return its SSE event stream (shared by
    /execute/debug and /execute/debug/audio)."""
    # The stream is created inside WorkflowExecutor._preparation_phase.
    # Pass workflow_id rather than the object: SQLAlchemy objects are bound to
    # a session, and run_workflow_isolated opens its own DB session.
    from assemblix_api.execution.background_tasks import background_task_registry

    _sse_task = asyncio.create_task(
        run_workflow_isolated(
            workflow_id=workflow.id,
            input_data=input_data,
            token_id=token_id,
            chat_session_id=session_id,
            audio_input=audio_input,
        )
    )
    background_task_registry.track(_sse_task)

    async def event_generator():
        execution_id = None
        try:
            # Wait up to 10 s for WorkflowExecutor to create the execution and stream
            queue = None

            for _ in range(100):  # 100 × 0.1 s = 10 s
                await asyncio.sleep(0.1)

                for exec_id in list(debug_event_manager._streams.keys()):
                    execution_id = exec_id
                    queue = debug_event_manager.get_stream(exec_id)
                    break

                if queue:
                    break

            if not execution_id:
                yield "event: error\n"
                yield f"data: {json.dumps({'error': 'Timeout waiting for execution to start'})}\n\n"
                return

            # Signal the executor that the SSE client is connected
            debug_event_manager.mark_client_ready(execution_id)

            # Send initial execution_started event
            initial_event = {
                "event_type": "execution_started",
                "execution_id": str(execution_id),
                "workflow_id": str(workflow.id),
                "timestamp": datetime.now().isoformat(),
                "session_id": str(session_id) if session_id else None,
            }
            yield "event: execution_started\n"
            yield f"data: {json.dumps(initial_event)}\n\n"

            if debug_event_manager.has_redis_transport:
                # Redis path: the transport streams payloads from Pub/Sub and stops
                # automatically after a terminal event (execution_complete / error).
                transport = debug_event_manager._redis_transport
                subscription = transport.subscribe(execution_id).__aiter__()
                while True:
                    try:
                        payload = await asyncio.wait_for(subscription.__anext__(), timeout=30.0)
                    except StopAsyncIteration:
                        break
                    except TimeoutError:
                        # No event within 30 s: ping so idle proxies keep the connection.
                        yield ": keepalive\n\n"
                        continue
                    yield f"event: {payload['event_type']}\n"
                    yield f"data: {json.dumps(payload)}\n\n"
            else:
                # In-process path: drain the asyncio.Queue with a 30-s keepalive.
                assert queue is not None  # set in the discovery loop above
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)

                        event_json = json.dumps(event.model_dump(), default=str)
                        yield f"event: {event.event_type.value}\n"
                        yield f"data: {event_json}\n\n"

                        if event.event_type.value in ["execution_complete", "error"]:
                            break

                    except TimeoutError:
                        yield ": keepalive\n\n"

        except asyncio.CancelledError:
            # Client disconnected
            pass
        except Exception as e:
            logger.exception("execution.event_generator_failed", error=str(e))
        finally:
            if execution_id:
                debug_event_manager.cleanup_stream(execution_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def _parse_execute_payload(payload: str) -> ExecuteWorkflowRequest:
    """Parse the multipart ``payload`` form field (JSON of ExecuteWorkflowRequest).

    The audio endpoints carry the request body as one JSON string alongside the
    file part, so the whole ``ExecuteWorkflowRequest`` DTO is reused verbatim.
    """
    try:
        return ExecuteWorkflowRequest.model_validate_json(payload)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid execute payload",
        ) from e


@router.post(
    "/{workflow_id}/execute",
    response_model=ExecutionResponse | ExecutionErrorResponse | TaskExecutionResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_workflow(
    workflow_id: UUID,
    request: ExecuteWorkflowRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    project_id_from_token: UUID = Depends(get_project_id_from_token),
    token_id: UUID = Depends(get_token_id_from_request),
    billing_service: BillingService = Depends(get_billing_service),
    chat_service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
    execution_service: ExecutionService = Depends(get_execution_service),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Execute a workflow with the given input data.

    Supports:
    - **Stateless execution**: no state persistence (session_id=None, create_session=False)
    - **Stateful execution**: continue an existing session (session_id provided)
    - **Create session**: create a new chat session (create_session=True)
    - **Task mode** (task=True): return execution_id immediately, result via polling

    Returns:
        200 ExecutionResponse — synchronous completion (task=False, finished within timeout)
        202 TaskExecutionResponse — async mode (task=True or timeout exceeded)
    """
    workflow = await _load_and_authorize(
        workflow_id,
        project_id_from_token=project_id_from_token,
        session_id=request.session_id,
        resolve_published=True,
        workflow_service=workflow_service,
        chat_service=chat_service,
        billing_service=billing_service,
        project_service=project_service,
    )

    input_data = _build_input_data(request, is_debug=False)

    return await _dispatch_sync(
        workflow,
        input_data,
        request=request,
        project_id=project_id_from_token,
        token_id=token_id,
        execution_service=execution_service,
        session=session,
    )


@router.post(
    "/{workflow_id}/execute/debug",
    status_code=status.HTTP_200_OK,
)
async def execute_workflow_debug(
    workflow_id: UUID,
    request: ExecuteWorkflowRequest,
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    debug_event_manager: DebugEventManager = Depends(get_debug_event_manager),
    project_id_from_token: UUID = Depends(get_project_id_from_token_with_access_check),
    token_id: UUID | None = Depends(get_token_id_optional),
    billing_service: BillingService = Depends(get_billing_service),
    chat_service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Execute a workflow in debug mode with real-time SSE streaming.

    Starts the workflow and immediately returns an SSE stream of execution
    events in real time.

    Returns:
        StreamingResponse with Content-Type: text/event-stream
    """
    workflow = await _load_and_authorize(
        workflow_id,
        project_id_from_token=project_id_from_token,
        session_id=request.session_id,
        resolve_published=False,
        workflow_service=workflow_service,
        chat_service=chat_service,
        billing_service=billing_service,
        project_service=project_service,
        current_user=current_user,
    )

    input_data = _build_input_data(request, is_debug=True)

    return _dispatch_debug_stream(
        workflow,
        input_data,
        session_id=request.session_id,
        token_id=token_id,
        debug_event_manager=debug_event_manager,
    )


@router.post(
    "/{workflow_id}/execute/audio",
    response_model=ExecutionResponse | ExecutionErrorResponse | TaskExecutionResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_workflow_audio(
    workflow_id: UUID,
    file: UploadFile = File(..., description="Audio blob for the run input"),
    payload: str = Form("{}", description="JSON of ExecuteWorkflowRequest (without audio)"),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    project_id_from_token: UUID = Depends(get_project_id_from_token),
    token_id: UUID = Depends(get_token_id_from_request),
    billing_service: BillingService = Depends(get_billing_service),
    chat_service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
    execution_service: ExecutionService = Depends(get_execution_service),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Execute a workflow from an audio message (multipart).

    Same contract as ``POST /execute`` but the run input is raw audio. The target
    workflow's START node must have ``acceptVoice=true`` (else 400); the audio is
    loaded onto the execution context (``input.input_type == "audio"``) — it is
    no longer transcribed here, downstream nodes (e.g. an explicit ``transcribe``
    node) consume it as needed.
    """
    request = _parse_execute_payload(payload)

    workflow = await _load_and_authorize(
        workflow_id,
        project_id_from_token=project_id_from_token,
        session_id=request.session_id,
        resolve_published=True,
        workflow_service=workflow_service,
        chat_service=chat_service,
        billing_service=billing_service,
        project_service=project_service,
    )

    input_data = _build_input_data(request, is_debug=False)

    audio_input = await load_audio_into_input_data(
        workflow=workflow, input_data=input_data, file=file
    )

    return await _dispatch_sync(
        workflow,
        input_data,
        request=request,
        project_id=project_id_from_token,
        token_id=token_id,
        execution_service=execution_service,
        session=session,
        audio_input=audio_input,
    )


@router.post(
    "/{workflow_id}/execute/debug/audio",
    status_code=status.HTTP_200_OK,
)
async def execute_workflow_debug_audio(
    workflow_id: UUID,
    file: UploadFile = File(..., description="Audio blob for the run input"),
    payload: str = Form("{}", description="JSON of ExecuteWorkflowRequest (without audio)"),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    debug_event_manager: DebugEventManager = Depends(get_debug_event_manager),
    project_id_from_token: UUID = Depends(get_project_id_from_token_with_access_check),
    token_id: UUID | None = Depends(get_token_id_optional),
    billing_service: BillingService = Depends(get_billing_service),
    chat_service: ChatService = Depends(get_chat_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Execute a workflow from an audio message in debug mode (multipart → SSE).

    The audio-input twin of ``POST /execute/debug``: loads the blob onto the
    execution context (START must have ``acceptVoice=true``; no transcription
    happens here), then streams the run's SSE events exactly as the text debug
    endpoint does.
    """
    request = _parse_execute_payload(payload)

    workflow = await _load_and_authorize(
        workflow_id,
        project_id_from_token=project_id_from_token,
        session_id=request.session_id,
        resolve_published=False,
        workflow_service=workflow_service,
        chat_service=chat_service,
        billing_service=billing_service,
        project_service=project_service,
        current_user=current_user,
    )

    input_data = _build_input_data(request, is_debug=True)

    audio_input = await load_audio_into_input_data(
        workflow=workflow, input_data=input_data, file=file
    )

    return _dispatch_debug_stream(
        workflow,
        input_data,
        session_id=request.session_id,
        token_id=token_id,
        debug_event_manager=debug_event_manager,
        audio_input=audio_input,
    )


@router.get(
    "/task/{execution_id}",
    response_model=TaskExecutionResponse | ExecutionResponse | ExecutionErrorResponse,
    status_code=status.HTTP_200_OK,
)
async def get_task_execution_result(
    execution_id: UUID,
    project_id_from_token: UUID = Depends(get_project_id_from_token_with_access_check),
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """
    Get the result of an async workflow execution (polling).

    Used after starting with task=True, or when a workflow exceeded TASK_TIMEOUT_SECONDS.

    Returns:
        200 TaskExecutionResponse — still running (status="running")
        200 ExecutionResponse — completed successfully
        200 ExecutionErrorResponse — completed with an error
    """
    return await execution_service.get_task_result(
        execution_id=execution_id,
        project_id=project_id_from_token,
    )


@execution_detail_router.get(
    "/in-flight",
    response_model=list[InFlightExecutionResponse],
    summary="List in-flight executions",
)
async def in_flight_executions(
    project_id_from_token: UUID = Depends(get_project_id_from_token_with_access_check),
    execution_service: ExecutionService = Depends(get_execution_service),
) -> list[InFlightExecutionResponse]:
    """
    List executions that are currently QUEUED or RUNNING for the caller's project.

    The project is determined from the API key / JWT token — no explicit project_id
    query parameter is required. Returns a lightweight summary (id, workflow_id, status,
    started_at, steps_count) suitable for a live dashboard or queue-depth monitor.

    Per-step token/cost/duration details are available via GET /executions/{id}.

    Returns:
        List of InFlightExecutionResponse, ordered oldest-first (by created_at).
    """
    return await execution_service.get_in_flight(project_id=project_id_from_token)


@execution_detail_router.get("/", response_model=PaginatedResponse[ExecutionInfoResponse])
async def list_executions(
    project_id: UUID | None = Query(
        default=None,
        description="Project ID. Optional when authenticated with a project-scoped "
        "API key — defaults to the key's project.",
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, ge=1, le=100, description="Page size"),
    workflow_id: UUID | None = Query(default=None, description="Filter by workflow ID"),
    chat_session_id: UUID | None = Query(default=None, description="Filter by chat session ID"),
    client_id: str | None = Query(default=None, description="Filter by client_id"),
    status: ExecutionStatus | None = Query(default=None, description="Filter by status"),
    date_from: datetime | None = Query(default=None, description="Filter by start date (ISO 8601)"),
    date_to: datetime | None = Query(default=None, description="Filter by end date (ISO 8601)"),
    include_debug: bool = Query(
        default=False,
        description="Include debug executions (excluded by default)",
    ),
    auth: AuthContext = Depends(get_auth_context),
    execution_service: ExecutionService = Depends(get_execution_service),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    List a project's executions with filtering and pagination.

    Supports filtering by:
    - workflow_id: a specific workflow
    - chat_session_id: a specific chat session
    - client_id: client identifier (via ClientSession)
    - status: execution status (running, completed, failed)
    - date_from/date_to: range of execution start dates
    - include_debug: whether to show debug executions
    """
    project_id = resolve_project_id(project_id, auth)
    await project_service.authorize_project_access(auth, project_id)

    offset = (page - 1) * limit

    # Resolve client_session_id when a client_id is provided
    client_session_id_value = None
    if client_id:
        client_session = await client_session_service.get_by_client_id(project_id, client_id)
        if client_session:
            client_session_id_value = client_session.id

    filters = ExecutionFilters(
        workflow_id=workflow_id,
        chat_session_id=chat_session_id,
        client_session_id=client_session_id_value,
        status=status,
        date_from=date_from,
        date_to=date_to,
        include_debug=include_debug,
    )

    executions, total = await execution_service.get_executions_list(
        project_id=project_id,
        offset=offset,
        limit=limit,
        filters=filters,
    )

    return PaginatedResponse(
        data=executions,
        total=total,
        page=page,
        limit=limit,
    )


@execution_detail_router.get("/{execution_id}", response_model=ExecutionDetailInfoResponse)
async def get_execution_detail(
    execution_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """
    Get full information about a workflow execution.

    Returns detailed execution info, including:
    - Base info (status, timing, metrics, state snapshots)
    - Detailed trace of all steps (ExecutionSteps) with inputs/outputs
    - Workflow info (name, configuration)
    - Chat session info (if the execution ran within a chat)

    The project is derived from the execution itself; access is checked by the
    user's membership in the project's organization. No X-Project-Id header is required.
    """
    return await execution_service.get_execution_detail(
        execution_id=execution_id,
        current_user=auth.user,
        scoped_project_id=auth.scoped_project_id,
    )


@execution_detail_router.get("/{execution_id}/stream")
async def stream_execution_events(
    execution_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    execution_service: ExecutionService = Depends(get_execution_service),
    debug_event_manager: DebugEventManager = Depends(get_debug_event_manager),
) -> StreamingResponse:
    """Subscribe to an execution's event stream (step events + text deltas) over SSE.

    Replays from the ``Last-Event-ID`` cursor, then tails live until the terminal event.
    404 when no live buffer exists (expired or a non-streaming run) — the client then falls
    back to GET /workflows/task/{execution_id} for the final result.
    """
    # Authorize: raises 404 if the execution is unknown, 403 if not in the caller's project.
    await execution_service.get_execution_detail(
        execution_id=execution_id,
        current_user=auth.user,
        scoped_project_id=auth.scoped_project_id,
    )

    # A task=true run returns its id before the executor opens the buffer; wait briefly.
    for _ in range(200):  # up to ~10s
        if debug_event_manager.is_streaming(execution_id):
            break
        await asyncio.sleep(0.05)
    if not debug_event_manager.is_streaming(execution_id):
        raise HTTPException(status_code=404, detail="No active stream for this execution")

    last_event_id = request.headers.get("last-event-id")
    try:
        cursor = int(last_event_id) if last_event_id else int(request.query_params.get("cursor", 0))
    except (TypeError, ValueError):
        cursor = 0

    async def event_generator():
        subscription = debug_event_manager.subscribe(execution_id, after_seq=cursor).__aiter__()
        while True:
            try:
                event = await asyncio.wait_for(subscription.__anext__(), timeout=25.0)
            except StopAsyncIteration:
                break
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield (
                f"id: {event.seq}\n"
                f"event: {event.event_type.value}\n"
                f"data: {event.model_dump_json()}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
