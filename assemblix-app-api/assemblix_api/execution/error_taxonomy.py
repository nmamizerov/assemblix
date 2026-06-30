"""Error taxonomy — classifies exceptions as transient / fatal / unknown.

Only TRANSIENT errors (429/5xx/timeout/connection drop) are worth retrying;
FATAL ones (config, validation, auth, logic) must fail immediately.

Deliberately low-level: imports only litellm/httpx and domain exceptions, never
workflow_executor/nodes, to avoid import cycles.
"""

import httpx
import litellm
from pydantic_ai.exceptions import ModelHTTPError

from assemblix_api.core.cel_evaluator import CELEvaluationError
from assemblix_api.enums import TransienceClass
from assemblix_api.execution.exceptions import (
    AgentRunTimeoutError,
    ExecutionError,
    MaxStepsExceededError,
    NodeExecutionError,
    NodeExecutionLimitError,
    NodeNotFoundError,
    WorkflowTimeoutError,
)

# Transient LLM provider failures — worth retrying.
_TRANSIENT_LITELLM: tuple[type[Exception], ...] = (
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.APIConnectionError,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
)

# Terminal provider errors — retry won't help (key, request, model).
_FATAL_LITELLM: tuple[type[Exception], ...] = (
    litellm.AuthenticationError,
    litellm.BadRequestError,
    litellm.NotFoundError,
    litellm.ContextWindowExceededError,
)

# Internal execution errors that are definitely fatal (config/logic/cycles).
_FATAL_INTERNAL: tuple[type[Exception], ...] = (
    NodeNotFoundError,
    MaxStepsExceededError,
    NodeExecutionLimitError,
    CELEvaluationError,
    # FATAL: the loop may have already executed tools, so a retry would repeat side effects.
    AgentRunTimeoutError,
)


def _first_real_cause(exc: BaseException) -> BaseException:
    """Unwrap an ExceptionGroup (e.g. FallbackModel's FallbackExceptionGroup) to its
    first concrete cause. No-op for non-group exceptions."""
    inner: BaseException | None = exc
    while isinstance(inner, BaseExceptionGroup) and inner.exceptions:
        inner = inner.exceptions[0]
    return inner if inner is not None else exc


def classify_error(exc: Exception) -> TransienceClass:
    """Classify an exception as transient (retryable), fatal, or unknown.

    NodeExecutionError is unwrapped to its original cause first. UNKNOWN is
    returned for unrecognized errors and the caller must treat it as fatal.
    """
    if isinstance(exc, NodeExecutionError):
        exc = exc.original_error

    # Unwrap an ExceptionGroup (FallbackModel raises one when all models fail) to its cause.
    unwrapped = _first_real_cause(exc)
    if isinstance(unwrapped, Exception):
        exc = unwrapped

    # Internal execution errors. Wall-clock budget overrun is potentially resumable.
    if isinstance(exc, WorkflowTimeoutError):
        return TransienceClass.TRANSIENT
    if isinstance(exc, _FATAL_INTERNAL):
        return TransienceClass.FATAL

    # HTTP node (httpx)
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429 or code >= 500:
            return TransienceClass.TRANSIENT
        return TransienceClass.FATAL
    # TransportError covers timeouts, connection drops, network errors.
    if isinstance(exc, httpx.TransportError):
        return TransienceClass.TRANSIENT

    # LLM provider (litellm)
    if isinstance(exc, _TRANSIENT_LITELLM):
        return TransienceClass.TRANSIENT
    if isinstance(exc, _FATAL_LITELLM):
        return TransienceClass.FATAL

    # --- Pydantic AI may wrap a litellm error into ModelHTTPError ---
    # (matters for FallbackModel.fallback_on, which sees the already-wrapped exception).
    if isinstance(exc, ModelHTTPError):
        if exc.status_code == 429 or exc.status_code >= 500:
            return TransienceClass.TRANSIENT
        return TransienceClass.FATAL

    # Other domain execution errors without explicit classification are fatal.
    if isinstance(exc, ExecutionError):
        return TransienceClass.FATAL

    return TransienceClass.UNKNOWN
