"""Application settings."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

load_dotenv()

_REDIS_SCHEMES = ("redis://", "rediss://", "unix://")


class Settings(BaseSettings):
    """Application configuration."""

    app_name: str = "Assemblix API"
    app_version: str = "0.1.0"
    debug: bool = False

    # PostgreSQL database settings
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://agent-flux:agent-flux@localhost:5412/agent-flux"
    )

    # SQLAlchemy connection-pool tuning — override via env for worker-tier deploys.
    db_echo: bool = False  # Log SQL queries to stdout.
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "10"))  # Persistent connections per process.
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))  # Extra burst connections.
    db_pool_timeout: int = int(
        os.getenv("DB_POOL_TIMEOUT", "30")
    )  # Seconds to wait for a free connection.
    # Disable asyncpg's prepared-statement cache. Required when the async engine
    # talks to a transaction-mode pooler (PgBouncer/Supavisor), which multiplexes
    # server connections and breaks prepared statements (DuplicatePreparedStatementError).
    # Keep False for the self-host default (direct Postgres, prepared statements on).
    db_disable_statement_cache: bool = (
        os.getenv("DB_DISABLE_STATEMENT_CACHE", "false").lower() == "true"
    )

    # Intentional bind on all interfaces for containerized / self-host deploys.
    host: str = "0.0.0.0"  # nosec B104
    port: int = 8000

    # CORS: comma-separated list of allowed origins.
    cors_allowed_origins: str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    )

    # Auth / JWT
    # Required secret — the app refuses to start without it (see validate_security_config).
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")  # 24 hours
    )

    # Encryption
    encryption_key: str = os.getenv(
        "ENCRYPTION_KEY",
        "",  # Must be set in .env for security
    )

    # LLM Config
    openai_api_base_url: str = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
    gemini_api_base_url: str = os.getenv(
        "GEMINI_API_BASE_URL", "https://gemini-proxy.skillslab.center"
    )

    # Tools Config
    tavily_api_key: str = os.getenv(
        "TAVILY_API_KEY",
        "",  # Get free API key from https://tavily.com
    )

    # System API Keys (for the FREE plan and as a fallback for PRO/BUSINESS)
    system_openai_api_key: str = os.getenv("SYSTEM_OPENAI_API_KEY", "")
    system_gemini_api_key: str = os.getenv("SYSTEM_GEMINI_API_KEY", "")
    system_deepseek_api_key: str = os.getenv("SYSTEM_DEEPSEEK_API_KEY", "")

    # Credit System Config (all prices in USD!)
    credit_value_usd: float = float(
        os.getenv("CREDIT_VALUE_USD", "0.0001")
    )  # Price of 1 credit in USD
    credit_margin_percent: int = int(os.getenv("CREDIT_MARGIN_PERCENT", "10"))  # LLM margin (%)
    request_fee_usd: float = float(
        os.getenv("REQUEST_FEE_USD", "0.0001")
    )  # Price per request in USD

    # OAuth Config
    google_oauth_client_id: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    google_oauth_client_secret: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    github_oauth_client_id: str = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
    github_oauth_client_secret: str = os.getenv("GITHUB_OAUTH_CLIENT_SECRET", "")

    # Billing / Payments
    # Paid billing is an Enterprise feature, off by default for self-host:
    # when false the /payments router is not mounted (see api/rest/__init__.py).
    billing_enabled: bool = os.getenv("BILLING_ENABLED", "false").lower() == "true"

    # Payment Provider Config
    payment_provider: str = os.getenv("PAYMENT_PROVIDER", "paddle")  # paddle

    # Paddle Billing (Merchant of Record)
    paddle_api_key: str = os.getenv("PADDLE_API_KEY", "")
    paddle_webhook_secret: str = os.getenv("PADDLE_WEBHOOK_SECRET", "")
    paddle_environment: str = os.getenv("PADDLE_ENVIRONMENT", "sandbox")
    paddle_price_starter: str = os.getenv("PADDLE_PRICE_STARTER", "")
    paddle_price_pro: str = os.getenv("PADDLE_PRICE_PRO", "")

    # Host URL for webhooks
    host_url: str = os.getenv("HOST_URL", "http://localhost:8000")

    # Notifications
    # Custom base URL for the Telegram Bot API (e.g. a proxy / local server).
    # Empty falls back to the standard https://api.telegram.org.
    telegram_api_base_url: str = os.getenv("TELEGRAM_API_BASE_URL", "")

    # SSRF: allow the HTTP node to reach internal/private addresses. For self-host
    # setups where workflows call local services. Off by default.
    http_node_allow_internal: bool = (
        os.getenv("HTTP_NODE_ALLOW_INTERNAL", "false").lower() == "true"
    )

    # Task execution timeout (seconds). If a workflow with task=False does not finish
    # within this time, a 202 TaskExecutionResponse is returned and execution continues
    # in the background.
    task_timeout_seconds: int = int(os.getenv("TASK_TIMEOUT_SECONDS", "60"))

    # Phase 4: how long to wait for in-flight executions to finish on SIGTERM.
    graceful_shutdown_timeout_seconds: int = int(
        os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS", "30")
    )

    # Horizontal scaling knobs (tunable per-deploy without rebuilding the image).
    # Max workflow jobs a single Arq worker process runs concurrently. Workflows are
    # I/O-bound (LLM/HTTP awaits), so a worker holds many cheaply; raise for more
    # per-process throughput, or add worker replicas. Keep <= DB pool unless the
    # executor uses short-lived per-node sessions (see queue/jobs.py).
    worker_max_jobs: int = int(os.getenv("WORKER_MAX_JOBS", "10"))
    # Number of uvicorn worker processes for the API tier (uvicorn --workers).
    web_concurrency: int = int(os.getenv("WEB_CONCURRENCY", "1"))
    # Whether the worker exposes its own Prometheus scrape port. Disable when running
    # multiple worker replicas on one host to avoid METRICS_PORT bind collisions.
    worker_metrics_enabled: bool = os.getenv("WORKER_METRICS_ENABLED", "true").lower() == "true"
    # Cross-worker concurrency caps (Redis-backed; require REDIS_URL). 0 = unlimited.
    # org cap: max concurrent agent (LLM) calls for one organization — stops one tenant
    # from starving the worker pool. provider cap: max concurrent calls to one LLM
    # provider (openai/gemini/...) — protects shared provider rate limits.
    org_max_concurrency: int = int(os.getenv("ORG_MAX_CONCURRENCY", "0"))
    provider_max_concurrency: int = int(os.getenv("PROVIDER_MAX_CONCURRENCY", "0"))
    # How long to wait for a free concurrency slot before proceeding anyway (backpressure,
    # never fails the workflow). Also bounds the slot TTL safety net.
    concurrency_acquire_timeout_seconds: float = float(
        os.getenv("CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS", "30")
    )

    # Phase 4: Redis is optional. When unset, the app runs single-process with
    # in-memory rate-limit and debug streams (default self-host mode).
    redis_url: str | None = os.getenv("REDIS_URL") or None
    execution_queue_enabled: bool = os.getenv("EXECUTION_QUEUE_ENABLED", "false").lower() == "true"
    debug_events_use_redis: bool = os.getenv("DEBUG_EVENTS_USE_REDIS", "false").lower() == "true"
    execution_checkpointing_enabled: bool = (
        os.getenv("EXECUTION_CHECKPOINTING_ENABLED", "false").lower() == "true"
    )
    login_rate_limit_per_5min: int = int(os.getenv("LOGIN_RATE_LIMIT_PER_5MIN", "10"))

    # Global wall-clock limit for a single workflow run (seconds). Guards against
    # never-ending workflows (agent loops, slow external calls).
    workflow_execution_timeout_seconds: int = int(
        os.getenv("WORKFLOW_EXECUTION_TIMEOUT_SECONDS", "1800")  # 30 minutes
    )

    # CEL: timeout for evaluating a single expression (seconds) — CPU-DoS protection.
    cel_evaluation_timeout_seconds: float = float(os.getenv("CEL_EVALUATION_TIMEOUT_SECONDS", "5"))

    # Execution reliability (Phase 3): retries / timeouts for LLM and HTTP calls.
    # These are node-level defaults; every node may override them in its own config.
    # Timeout for a single LLM call (seconds) — forwarded to litellm `timeout`.
    llm_request_timeout_seconds: float = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "60"))
    # How many times litellm retries a transient error of one LLM call (litellm `num_retries`).
    llm_num_retries: int = int(os.getenv("LLM_NUM_RETRIES", "2"))
    # Ceiling for the whole agent loop of a single agent node (seconds, wall-clock).
    # Must be <= workflow_execution_timeout_seconds.
    agent_run_timeout_seconds: float = float(os.getenv("AGENT_RUN_TIMEOUT_SECONDS", "300"))
    # How many times to retry transient HTTP-node failures (via tenacity).
    http_node_num_retries: int = int(os.getenv("HTTP_NODE_NUM_RETRIES", "2"))

    # Limits for uploading documents to the knowledge base.
    kb_max_upload_bytes: int = int(
        os.getenv("KB_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))  # 25 MB
    )
    kb_max_pdf_pages: int = int(os.getenv("KB_MAX_PDF_PAGES", "500"))
    kb_pdf_parse_timeout_seconds: float = float(os.getenv("KB_PDF_PARSE_TIMEOUT_SECONDS", "30"))

    # Phase 5: Observability / Prometheus metrics.
    # When true, the /metrics endpoint and worker scrape port are enabled.
    metrics_enabled: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    # Port the worker process exposes for Prometheus scraping (standalone HTTP server).
    metrics_port: int = int(os.getenv("METRICS_PORT", "9000"))

    @field_validator("redis_url", mode="after")
    @classmethod
    def _normalise_redis_url(cls, value: str | None) -> str | None:
        """Treat any non-Redis-scheme value as unset (single-process default).

        Docker Compose's env_file parser keeps inline ``# ...`` comments as part
        of the value, so a blank-but-commented ``REDIS_URL=`` line arrives as a
        comment string. Guard against that (and stray whitespace) so the app
        doesn't try to open a bogus connection.
        """
        raw = (value or "").strip()
        return raw if raw.startswith(_REDIS_SCHEMES) else None

    class Config:
        # Single source of truth is the repo-root `.env` (one dir up from the
        # api package, where `make dev` / scripts run). A local `.env` in the
        # api dir, if present, takes precedence as an override.
        env_file = ("../.env", ".env")
        case_sensitive = False
        extra = "allow"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_security_config(settings: Settings) -> None:
    """Fail-fast validation of critical secrets, called on application startup.

    Raises RuntimeError if:
    - JWT_SECRET_KEY is empty or shorter than 32 chars (token forgery risk);
    - ENCRYPTION_KEY is empty or not a valid Fernet key (otherwise credentials
      could be stored in plaintext / fail to decrypt).
    """
    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY is missing or too short (min 32 chars). "
            'Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )

    if not settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY is required. Generate one: python generate_encryption_key.py"
        )

    try:
        from cryptography.fernet import Fernet

        Fernet(settings.encryption_key.encode())
    except Exception as exc:
        raise RuntimeError(
            "ENCRYPTION_KEY is not a valid Fernet key. "
            "Generate one: python generate_encryption_key.py"
        ) from exc
