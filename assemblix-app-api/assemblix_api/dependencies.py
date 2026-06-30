"""FastAPI dependency injection wiring."""

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.billing.credit_service import CreditService
from assemblix_api.billing.rate_limit_service import RateLimitService
from assemblix_api.billing.service import BillingService
from assemblix_api.core.cel_evaluator import CELEvaluator
from assemblix_api.core.node_registry import NodeRegistry
from assemblix_api.database import get_async_session
from assemblix_api.database.models.organization import Organization
from assemblix_api.database.models.user import User
from assemblix_api.database.repositories.api_key_repository import APIKeyRepository
from assemblix_api.database.repositories.chat_message_repository import (
    ChatMessageRepository,
)
from assemblix_api.database.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from assemblix_api.database.repositories.client_session_repository import (
    ClientSessionRepository,
)
from assemblix_api.database.repositories.credentials_repository import (
    CredentialsRepository,
)
from assemblix_api.database.repositories.credit_transaction_repository import (
    CreditTransactionRepository,
)
from assemblix_api.database.repositories.execution_repository import ExecutionRepository
from assemblix_api.database.repositories.execution_step_repository import (
    ExecutionStepRepository,
)
from assemblix_api.database.repositories.knowledge_base_repository import (
    KnowledgeBaseRepository,
)
from assemblix_api.database.repositories.knowledge_document_repository import (
    KnowledgeDocumentRepository,
)
from assemblix_api.database.repositories.node_template_repository import (
    NodeTemplateRepository,
)
from assemblix_api.database.repositories.notification_channel_repository import (
    NotificationChannelRepository,
)
from assemblix_api.database.repositories.organization_repository import (
    OrganizationRepository,
)
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.database.repositories.payment_repository import PaymentRepository
from assemblix_api.database.repositories.project_repository import ProjectRepository
from assemblix_api.database.repositories.user_repository import UserRepository
from assemblix_api.database.repositories.workflow_repository import WorkflowRepository
from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.execution.workflow_executor import WorkflowExecutor
from assemblix_api.services.api_key_service import APIKeyService
from assemblix_api.services.chat_message_service import ChatMessageService
from assemblix_api.services.chat_service import ChatService
from assemblix_api.services.client_session_service import ClientSessionService
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.execution_service import ExecutionService
from assemblix_api.services.execution_trace_service import ExecutionTracerService
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService
from assemblix_api.services.node_template_service import NodeTemplateService
from assemblix_api.services.notification_channel_service import (
    NotificationChannelService,
)
from assemblix_api.services.oauth_service import OAuthService
from assemblix_api.services.organization_service import OrganizationService
from assemblix_api.services.payment_service import PaymentService
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.user_service import UserService
from assemblix_api.services.workflow_service import WorkflowService

logger = structlog.get_logger(__name__)

# ============================================
# Arq Redis pool (optional — only when EXECUTION_QUEUE_ENABLED=true)
# ============================================

# Module-level singleton so the pool is created once per process.
_arq_pool = None


async def get_arq_pool():
    """
    Return a cached ArqRedis pool for job enqueueing.

    Returns None when the queue is disabled or Redis is not configured, so
    callers that only use it inside `if settings.execution_queue_enabled:` blocks
    never open a Redis connection in default self-host mode.

    arq is imported lazily here so the module can be loaded without arq being
    available / without Redis being configured.
    """
    global _arq_pool
    from assemblix_api.core.redis_client import is_redis_enabled
    from assemblix_api.core.settings import get_settings

    settings = get_settings()
    if not (is_redis_enabled() and settings.execution_queue_enabled):
        return None

    if _arq_pool is None:
        import arq  # noqa: PLC0415  — lazy import to avoid requiring arq at app load
        from arq.connections import RedisSettings

        _arq_pool = await arq.create_pool(RedisSettings.from_dsn(settings.redis_url))
        logger.info("arq_pool.created", redis_url=settings.redis_url)

    return _arq_pool


async def close_arq_pool() -> None:
    """Close the Arq pool if it was created. Called during lifespan shutdown."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None
        logger.info("arq_pool.closed")


# ============================================
# Database Session
# ============================================


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async for session in get_async_session():
        yield session


# ============================================
# Repositories
# ============================================


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


async def get_workflow_repository(
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowRepository:
    return WorkflowRepository(session)


async def get_credentials_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CredentialsRepository:
    return CredentialsRepository(session)


async def get_execution_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionRepository:
    return ExecutionRepository(session)


async def get_chat_session_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ChatSessionRepository:
    return ChatSessionRepository(session)


async def get_chat_message_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ChatMessageRepository:
    return ChatMessageRepository(session)


async def get_execution_step_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionStepRepository:
    return ExecutionStepRepository(session)


async def get_api_key_repository(
    session: AsyncSession = Depends(get_db_session),
) -> APIKeyRepository:
    return APIKeyRepository(session)


async def get_organization_repository(
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationRepository:
    return OrganizationRepository(session)


async def get_organization_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationUserRepository:
    return OrganizationUserRepository(session)


async def get_project_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRepository:
    return ProjectRepository(session)


async def get_client_session_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ClientSessionRepository:
    return ClientSessionRepository(session)


async def get_credit_transaction_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CreditTransactionRepository:
    return CreditTransactionRepository(session)


async def get_payment_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PaymentRepository:
    return PaymentRepository(session)


async def get_node_template_repository(
    session: AsyncSession = Depends(get_db_session),
) -> NodeTemplateRepository:
    return NodeTemplateRepository(session)


async def get_knowledge_base_repository(
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeBaseRepository:
    return KnowledgeBaseRepository(session)


async def get_knowledge_document_repository(
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeDocumentRepository:
    return KnowledgeDocumentRepository(session)


async def get_notification_channel_repository(
    session: AsyncSession = Depends(get_db_session),
) -> NotificationChannelRepository:
    return NotificationChannelRepository(session)


# ============================================
# Services
# ============================================


async def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
    organization_repository: OrganizationRepository = Depends(get_organization_repository),
    organization_user_repository: OrganizationUserRepository = Depends(
        get_organization_user_repository
    ),
    project_repository: ProjectRepository = Depends(get_project_repository),
) -> UserService:
    return UserService(
        user_repository,
        organization_repository,
        organization_user_repository,
        project_repository,
    )


async def get_oauth_service(
    user_repository: UserRepository = Depends(get_user_repository),
    organization_repository: OrganizationRepository = Depends(get_organization_repository),
    organization_user_repository: OrganizationUserRepository = Depends(
        get_organization_user_repository
    ),
    project_repository: ProjectRepository = Depends(get_project_repository),
) -> OAuthService:
    return OAuthService(
        user_repository,
        organization_repository,
        organization_user_repository,
        project_repository,
    )


async def get_credit_service(
    organization_repository: OrganizationRepository = Depends(get_organization_repository),
    transaction_repository: CreditTransactionRepository = Depends(
        get_credit_transaction_repository
    ),
) -> CreditService:
    return CreditService(
        organization_repository=organization_repository,
        transaction_repository=transaction_repository,
    )


# Singleton instance for RateLimitService
_rate_limit_service: RateLimitService | None = None


async def get_rate_limit_service() -> RateLimitService:
    """Async dependency for RateLimitService singleton.

    Selects Redis backend when REDIS_URL is configured, otherwise falls back to
    in-memory backend (safe for single-process self-host with no Redis).
    """
    global _rate_limit_service
    if _rate_limit_service is None:
        from assemblix_api.billing.rate_limit_backends import (
            InMemoryRateLimitBackend,
            RateLimitBackend,
            RedisRateLimitBackend,
        )
        from assemblix_api.core.redis_client import get_redis, is_redis_enabled

        backend: RateLimitBackend
        if is_redis_enabled():
            redis = await get_redis()
            backend = RedisRateLimitBackend(redis)
        else:
            backend = InMemoryRateLimitBackend()
        _rate_limit_service = RateLimitService(backend)
    return _rate_limit_service


async def get_billing_service(
    organization_repository: OrganizationRepository = Depends(get_organization_repository),
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
    credit_service: CreditService = Depends(get_credit_service),
    rate_limit_service: RateLimitService = Depends(get_rate_limit_service),
) -> BillingService:
    return BillingService(
        organization_repository=organization_repository,
        workflow_repository=workflow_repository,
        credit_service=credit_service,
        rate_limit_service=rate_limit_service,
    )


async def get_workflow_service(
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
    billing_service: BillingService = Depends(get_billing_service),
) -> WorkflowService:
    return WorkflowService(workflow_repository, billing_service)


async def get_credentials_service(
    credentials_repository: CredentialsRepository = Depends(get_credentials_repository),
    organization_user_repository: OrganizationUserRepository = Depends(
        get_organization_user_repository
    ),
) -> CredentialsService:
    return CredentialsService(credentials_repository, organization_user_repository)


async def get_chat_service(
    chat_session_repository: ChatSessionRepository = Depends(get_chat_session_repository),
) -> ChatService:
    return ChatService(chat_session_repository)


async def get_chat_message_service(
    chat_message_repository: ChatMessageRepository = Depends(get_chat_message_repository),
    chat_session_repository: ChatSessionRepository = Depends(get_chat_session_repository),
) -> ChatMessageService:
    return ChatMessageService(chat_message_repository, chat_session_repository)


async def get_client_session_service(
    client_session_repository: ClientSessionRepository = Depends(get_client_session_repository),
) -> ClientSessionService:
    return ClientSessionService(client_session_repository)


async def get_execution_tracer_service(
    execution_step_repository: ExecutionStepRepository = Depends(get_execution_step_repository),
) -> ExecutionTracerService:
    return ExecutionTracerService(execution_step_repository)


async def get_api_key_service(
    api_key_repository: APIKeyRepository = Depends(get_api_key_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    project_repository: ProjectRepository = Depends(get_project_repository),
    organization_repository: OrganizationRepository = Depends(get_organization_repository),
) -> APIKeyService:
    return APIKeyService(
        api_key_repository,
        user_repository,
        project_repository,
        organization_repository,
    )


async def get_organization_service(
    organization_repository: OrganizationRepository = Depends(get_organization_repository),
    organization_user_repository: OrganizationUserRepository = Depends(
        get_organization_user_repository
    ),
) -> OrganizationService:
    return OrganizationService(organization_repository, organization_user_repository)


async def get_project_service(
    project_repository: ProjectRepository = Depends(get_project_repository),
    organization_user_repository: OrganizationUserRepository = Depends(
        get_organization_user_repository
    ),
) -> ProjectService:
    return ProjectService(project_repository, organization_user_repository)


async def get_execution_service(
    execution_repository: ExecutionRepository = Depends(get_execution_repository),
    project_service: ProjectService = Depends(get_project_service),
) -> ExecutionService:
    return ExecutionService(execution_repository, project_service)


async def get_payment_service(
    payment_repository: PaymentRepository = Depends(get_payment_repository),
    organization_repository: OrganizationRepository = Depends(get_organization_repository),
    credit_service: CreditService = Depends(get_credit_service),
) -> PaymentService:
    return PaymentService(
        payment_repository=payment_repository,
        organization_repository=organization_repository,
        credit_service=credit_service,
    )


async def get_node_template_service(
    node_template_repository: NodeTemplateRepository = Depends(get_node_template_repository),
) -> NodeTemplateService:
    return NodeTemplateService(node_template_repository)


async def get_knowledge_base_service(
    kb_repository: KnowledgeBaseRepository = Depends(get_knowledge_base_repository),
    doc_repository: KnowledgeDocumentRepository = Depends(get_knowledge_document_repository),
) -> KnowledgeBaseService:
    return KnowledgeBaseService(kb_repository, doc_repository)


async def get_notification_channel_service(
    notification_channel_repository: NotificationChannelRepository = Depends(
        get_notification_channel_repository
    ),
) -> NotificationChannelService:
    return NotificationChannelService(notification_channel_repository)


# ============================================
# Core Components
# ============================================


def get_node_registry() -> NodeRegistry:
    return NodeRegistry()


def get_cel_evaluator() -> CELEvaluator:
    return CELEvaluator()


# Singleton instance for DebugEventManager
_debug_event_manager: DebugEventManager | None = None


async def get_debug_event_manager() -> DebugEventManager:
    """Async dependency that returns the DebugEventManager singleton.

    When both REDIS_URL and DEBUG_EVENTS_USE_REDIS=true are set, the manager
    is constructed with a RedisDebugEventTransport so that debug events flow
    through Redis Pub/Sub (enabling cross-replica SSE).  Otherwise the plain
    in-process asyncio.Queue path is used — no Redis connection is attempted.
    """
    global _debug_event_manager
    if _debug_event_manager is None:
        from assemblix_api.core.redis_client import get_redis, is_redis_enabled
        from assemblix_api.core.settings import get_settings

        settings = get_settings()
        if is_redis_enabled() and settings.debug_events_use_redis:
            from assemblix_api.execution.debug_pubsub import RedisDebugEventTransport

            redis = await get_redis()
            _debug_event_manager = DebugEventManager(
                redis_transport=RedisDebugEventTransport(redis)
            )
        else:
            _debug_event_manager = DebugEventManager()
    return _debug_event_manager


# ============================================
# Workflow Executor
# ============================================


async def get_workflow_executor(
    execution_service: ExecutionService = Depends(get_execution_service),
    chat_service: ChatService = Depends(get_chat_service),
    tracer: ExecutionTracerService = Depends(get_execution_tracer_service),
    node_registry: NodeRegistry = Depends(get_node_registry),
    cel_evaluator: CELEvaluator = Depends(get_cel_evaluator),
    credential_service: CredentialsService = Depends(get_credentials_service),
    chat_message_service: ChatMessageService = Depends(get_chat_message_service),
    debug_event_manager: DebugEventManager = Depends(get_debug_event_manager),
    client_session_service: ClientSessionService = Depends(get_client_session_service),
    project_service: ProjectService = Depends(get_project_service),
    organization_service: OrganizationService = Depends(get_organization_service),
    credit_service: CreditService = Depends(get_credit_service),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> WorkflowExecutor:
    return WorkflowExecutor(
        execution_service=execution_service,
        chat_service=chat_service,
        tracer=tracer,
        node_registry=node_registry,
        cel_evaluator=cel_evaluator,
        credential_service=credential_service,
        chat_message_service=chat_message_service,
        debug_event_manager=debug_event_manager,
        client_session_service=client_session_service,
        project_service=project_service,
        organization_service=organization_service,
        credit_service=credit_service,
        knowledge_base_service=knowledge_base_service,
    )


async def build_executor(session: AsyncSession) -> WorkflowExecutor:
    """
    Wire all repositories and services for a given DB session and return a WorkflowExecutor.

    Extracted from run_workflow_isolated so that the Arq worker (queue/jobs.py) can
    reuse the same construction logic without duplicating it.

    Args:
        session: An open AsyncSession bound to the desired DB engine.

    Returns:
        A fully wired WorkflowExecutor ready to call .execute(...).
    """
    execution_repo = ExecutionRepository(session)
    chat_session_repo = ChatSessionRepository(session)
    chat_message_repo = ChatMessageRepository(session)
    execution_step_repo = ExecutionStepRepository(session)
    credentials_repo = CredentialsRepository(session)
    organization_user_repo = OrganizationUserRepository(session)
    client_session_repo = ClientSessionRepository(session)
    project_repo = ProjectRepository(session)
    organization_repo = OrganizationRepository(session)
    credit_transaction_repo = CreditTransactionRepository(session)
    kb_repo = KnowledgeBaseRepository(session)
    kb_doc_repo = KnowledgeDocumentRepository(session)

    project_service = ProjectService(project_repo, organization_user_repo)
    execution_service = ExecutionService(execution_repo, project_service)
    chat_service = ChatService(chat_session_repo)
    chat_message_service = ChatMessageService(chat_message_repo, chat_session_repo)
    tracer = ExecutionTracerService(execution_step_repo)
    credential_service = CredentialsService(credentials_repo, organization_user_repo)
    client_session_service = ClientSessionService(client_session_repo)
    organization_service = OrganizationService(organization_repo, organization_user_repo)
    credit_service = CreditService(organization_repo, credit_transaction_repo)
    knowledge_base_service = KnowledgeBaseService(kb_repo, kb_doc_repo)

    node_registry = NodeRegistry()
    cel_evaluator = CELEvaluator()
    debug_event_manager = await get_debug_event_manager()

    return WorkflowExecutor(
        execution_service=execution_service,
        chat_service=chat_service,
        tracer=tracer,
        node_registry=node_registry,
        cel_evaluator=cel_evaluator,
        credential_service=credential_service,
        chat_message_service=chat_message_service,
        debug_event_manager=debug_event_manager,
        client_session_service=client_session_service,
        project_service=project_service,
        organization_service=organization_service,
        credit_service=credit_service,
        knowledge_base_service=knowledge_base_service,
        # Lets the executor/nodes commit at node boundaries so the DB connection is
        # not pinned for the whole run (released during LLM/HTTP awaits). Safe only
        # because the queue/isolated sessions use expire_on_commit=False.
        db_checkpoint=session.commit,
    )


async def run_workflow_isolated(
    workflow_id: UUID,
    input_data: dict,
    token_id: UUID | None,
    chat_session_id: UUID | None,
    execution_id_future: asyncio.Future | None = None,
    result_future: asyncio.Future | None = None,
) -> None:
    """
    Run workflow execution in an isolated DB session.

    Used for background tasks (e.g. debug mode) where execution must be independent
    of the main request lifecycle. Creates its own DB session plus all necessary
    services, executes the workflow, and closes the session afterwards.

    NOTE: We accept workflow_id (not a workflow object) because SQLAlchemy objects
    are session-bound and cannot be reused across sessions.

    Args:
        workflow_id: ID of the workflow to execute
        input_data: Input data for the workflow
        token_id: API key ID (or None for debug mode)
        chat_session_id: Chat session ID (optional)
        execution_id_future: Future that receives the execution ID after it is created
        result_future: Future that receives the ExecutionResult on completion
    """
    from assemblix_api.database.engine import get_async_engine
    from assemblix_api.database.repositories.workflow_repository import (
        WorkflowRepository,
    )

    engine = get_async_engine()

    # expire_on_commit=False: the executor commits at node boundaries to release the DB
    # connection during LLM/HTTP awaits; the `execution`/`workflow` ORM objects must
    # survive those commits without a lazy async reload (MissingGreenlet).
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            workflow_repo = WorkflowRepository(session)
            # Keep a reference to execution_repo for post-commit notifications.
            execution_repo = ExecutionRepository(session)

            workflow = await workflow_repo.get_by_id(workflow_id)
            if not workflow:
                logger.warning("workflow.isolated.not_found", workflow_id=str(workflow_id))
                return

            executor = await build_executor(session)

            # Callback to propagate the execution ID back to the caller.
            async def on_execution_created(exec_id: UUID) -> None:
                if execution_id_future is not None and not execution_id_future.done():
                    execution_id_future.set_result(exec_id)

            result = await executor.execute(
                workflow=workflow,
                input_data=input_data,
                token_id=token_id,
                chat_session_id=chat_session_id,
                on_execution_created=on_execution_created,
            )

            if result_future is not None and not result_future.done():
                result_future.set_result(result)

            # Snap primitives off the workflow BEFORE commit: after commit the object
            # expires (expire_on_commit=True) and lazy attribute reads in an async
            # context would fail with MissingGreenlet.
            workflow_project_id = workflow.project_id
            workflow_name = workflow.name

            await session.commit()

            # Notify on a technical failure (prod executions only, status=FAILED),
            # fire-and-forget with its own session so it cannot block or break the run.
            await _maybe_notify_execution_failure(
                execution_repo,
                result.execution_id,
                project_id=workflow_project_id,
                workflow_name=workflow_name,
            )

        except Exception as e:
            await session.rollback()
            # The error was already handled in the executor and sent to the debug stream.
            logger.exception("workflow.isolated.execution_failed", error=str(e))


# Hold strong references to background notification tasks so the GC does not collect
# them before completion (asyncio keeps only weak references to tasks).
_notification_tasks: set[asyncio.Task] = set()


async def _maybe_notify_execution_failure(
    execution_repo: ExecutionRepository,
    execution_id: UUID,
    *,
    project_id: UUID,
    workflow_name: str,
) -> None:
    """Dispatch a notification if the execution ended with a technical error
    (status=FAILED) and it is NOT a debug run.

    Takes only primitives (project_id/workflow_name snapped before commit) and sends
    in the background so the actual delivery does not affect the execution lifecycle.
    """
    from assemblix_api.enums import ExecutionStatus
    from assemblix_api.services.notifications.dispatch import dispatch_execution_failure

    execution = await execution_repo.get_by_id(execution_id)
    if execution is None:
        return
    if execution.status != ExecutionStatus.FAILED or execution.is_debug:
        return

    task = asyncio.create_task(
        dispatch_execution_failure(
            project_id=project_id,
            execution_id=execution.id,
            workflow_name=workflow_name,
            error_type=(execution.error_type.value if execution.error_type else None),
            error_message=execution.error_message,
            failed_node_id=execution.failed_node_id,
        )
    )
    _notification_tasks.add(task)
    task.add_done_callback(_notification_tasks.discard)


# ============================================
# Authentication
# ============================================

_http_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    user_service: UserService = Depends(get_user_service),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> User:
    """Resolve the current authenticated user.

    A token starting with 'sk_' is verified as an API key; otherwise it is
    verified as a JWT.
    """
    token = credentials.credentials

    if token.startswith("sk_"):
        user = await api_key_service.verify_api_key(token)
        if user:
            structlog.contextvars.bind_contextvars(user_id=str(user.id), auth_method="api_key")
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный API ключ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await user_service.get_user_from_token(token)
    structlog.contextvars.bind_contextvars(user_id=str(user.id), auth_method="jwt")
    return user


async def get_current_organization(
    current_user: User = Depends(get_current_user),
    organization_service: OrganizationService = Depends(get_organization_service),
) -> Organization:
    """Resolve the user's current organization, verifying it is set and accessible."""
    if not current_user.current_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Текущая организация не установлена",
        )

    return await organization_service.verify_user_access(
        current_user, current_user.current_organization_id
    )


async def get_token_id_from_request(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> UUID:
    """Return the api_keys row ID for the request. Requires an API key (not a JWT)."""
    token = credentials.credentials

    if not token.startswith("sk_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Только API ключи поддерживаются для выполнения workflow",
        )
    api_key = await api_key_service.get_api_key_object(token)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный API ключ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key.id


async def get_token_id_optional(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> UUID | None:
    """Return the api_keys row ID, or None for JWT tokens (used in debug mode)."""
    token = credentials.credentials

    if not token.startswith("sk_"):
        return None

    api_key = await api_key_service.get_api_key_object(token)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный API ключ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key.id


async def get_project_id_from_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> UUID:
    """Resolve project_id: from the API key when token starts with 'sk_', otherwise
    from the X-Project-Id header (JWT)."""

    token = credentials.credentials

    if token.startswith("sk_"):
        api_key = await api_key_service.get_api_key_object(token)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный API ключ",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return api_key.project_id

    project_id_header = request.headers.get("X-Project-Id")
    if not project_id_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отсутствует хедер X-Project-Id для JWT токена",
        )

    try:
        return UUID(project_id_header)
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невалидный формат project_id в хедере X-Project-Id",
        ) from e


async def get_project_id_from_token_with_access_check(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    api_key_service: APIKeyService = Depends(get_api_key_service),
    user_service: UserService = Depends(get_user_service),
    project_service: ProjectService = Depends(get_project_service),
) -> UUID:
    """Like get_project_id_from_token, but for JWTs it also verifies the user has
    access to the project (API keys are scoped to a project and skip the check)."""

    token = credentials.credentials

    if token.startswith("sk_"):
        api_key = await api_key_service.get_api_key_object(token)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный API ключ",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return api_key.project_id

    project_id_header = request.headers.get("X-Project-Id")
    if not project_id_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отсутствует хедер X-Project-Id для JWT токена",
        )

    try:
        project_id = UUID(project_id_header)
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невалидный формат project_id в хедере X-Project-Id",
        ) from e

    user = await user_service.get_user_from_token(token)
    await project_service.verify_user_project_access(user, project_id)

    return project_id
