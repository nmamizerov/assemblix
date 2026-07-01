"""Enums for database models."""

from enum import Enum


class ExecutionStatus(str, Enum):
    """Execution status of a workflow run."""

    QUEUED = "QUEUED"  # Persisted to the queue, not yet picked up by a worker
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"  # Business-level error (agent intentional refusal)
    FAILED = "FAILED"  # Technical error (unexpected crash)


class StepStatus(str, Enum):
    """Execution status of a workflow step."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageRole(str, Enum):
    """Role of a chat message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class NodeType(str, Enum):
    START = "start"
    AGENT = "agent"
    CONDITION = "condition"
    SET_VARIABLE = "set_variable"
    END = "end"
    STICKER = "sticker"
    PLACEHOLDER = "placeholder"
    HTTP_REQUEST = "http_request"
    # Future types:
    # LOOP = "loop"
    # WEBHOOK = "webhook"
    # CODE = "code"


class ExecutionErrorType(str, Enum):
    """Error types for workflow execution."""

    CONFIGURATION_ERROR = "configuration"  # Invalid workflow/node configuration
    VALIDATION_ERROR = "validation"  # Data validation error
    RUNTIME_ERROR = "runtime"  # Runtime error (LLM API fail, network)
    TIMEOUT_ERROR = "timeout"  # Timeout exceeded
    CYCLE_DETECTION = "cycle_detection"  # Infinite loop detected
    LOGIC_ERROR = "logic"  # Logic error (no next node, etc)
    SYSTEM_ERROR = "system"  # System error (DB unavailable, etc)


class TransienceClass(str, Enum):
    """Error classification for retry decisions.

    - TRANSIENT: temporary failure (429/5xx/timeout/dropped connection) — retryable.
    - FATAL: configuration/validation/logic error — retrying is pointless, fail.
    - UNKNOWN: unclassified — treated as fatal (safe default).
    """

    TRANSIENT = "transient"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class AgentProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"


class PlanTier(str, Enum):
    """Subscription plan tiers."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"


class OAuthProvider(str, Enum):
    """OAuth providers for authentication."""

    GOOGLE = "google"
    GITHUB = "github"
    YANDEX = "yandex"


class KnowledgeDocumentSourceType(str, Enum):
    """Knowledge base document source type."""

    PDF = "pdf"
    TEXT = "text"


class NotificationChannelType(str, Enum):
    """Notification channel type."""

    TELEGRAM = "TELEGRAM"
    # SLACK = "SLACK"  # future
