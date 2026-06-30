"""Assemblix API - application entry point."""

from contextlib import asynccontextmanager

# Instrument once per process; create_app may run multiple times in tests.
_metrics_instrumented = False

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from assemblix_api.core.logging import configure_logging

configure_logging()

from assemblix_api.api.rest import api_router
from assemblix_api.api.rest.health import router as health_router
from assemblix_api.core.encryption import init_encryption_service
from assemblix_api.core.middleware.access_log import AccessLogMiddleware
from assemblix_api.core.settings import get_settings, validate_security_config
from assemblix_api.database import check_db_connection  # noqa: F401
from assemblix_api.execution.background_tasks import background_task_registry

settings = get_settings()
logger = structlog.get_logger("startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    # Fail-fast: the app won't start without valid JWT_SECRET_KEY and ENCRYPTION_KEY.
    validate_security_config(settings)
    init_encryption_service(settings.encryption_key)
    logger.info("startup.encryption_ready")

    from assemblix_api.core.node_loader import load_builtin_nodes, load_plugin_nodes
    from assemblix_api.core.node_registry import NodeRegistry

    load_builtin_nodes()
    plugins = load_plugin_nodes()
    logger.info(
        "startup.nodes_registered",
        types=NodeRegistry().registered_types(),
        plugins=plugins,
    )

    from assemblix_api.oauth.github import GitHubOAuthProvider
    from assemblix_api.oauth.google import GoogleOAuthProvider
    from assemblix_api.oauth.registry import OAuthProviderRegistry

    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        google_provider = GoogleOAuthProvider(
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
        )
        OAuthProviderRegistry.register("google", google_provider)
        logger.info("startup.oauth_registered", provider="google")
    else:
        logger.warning("startup.oauth_skipped", provider="google", reason="credentials_missing")

    if settings.github_oauth_client_id and settings.github_oauth_client_secret:
        github_provider = GitHubOAuthProvider(
            settings.github_oauth_client_id,
            settings.github_oauth_client_secret,
        )
        OAuthProviderRegistry.register("github", github_provider)
        logger.info("startup.oauth_registered", provider="github")
    else:
        logger.warning("startup.oauth_skipped", provider="github", reason="credentials_missing")

    yield

    # Graceful shutdown: wait for in-flight executions before the process exits,
    # so a deploy/SIGTERM does not silently drop running workflows.
    remaining = await background_task_registry.drain(
        timeout=settings.graceful_shutdown_timeout_seconds
    )
    logger.info("shutdown.complete", unfinished_tasks=remaining)

    # Close the Arq pool if it was created (no-op when queue is disabled).
    from assemblix_api.dependencies import close_arq_pool

    await close_arq_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Assemblix API with PostgreSQL",
        lifespan=lifespan,
        debug=settings.debug,
    )

    allowed_origins = [
        origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Project-Id"],
    )

    # Middleware stack: the last add_middleware is the outermost (runs first).
    # CorrelationIdMiddleware must be outermost so request_id is already in contextvars
    # by the time AccessLogMiddleware and the routers write logs.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # Health/readiness probes at root (no /api prefix — infra tooling expects these).
    app.include_router(health_router)

    # Metrics (gated by settings.metrics_enabled, on by default).
    if settings.metrics_enabled:
        global _metrics_instrumented
        if not _metrics_instrumented:
            try:
                from prometheus_fastapi_instrumentator import Instrumentator

                Instrumentator().instrument(app).expose(
                    app, endpoint="/metrics", include_in_schema=False
                )
                _metrics_instrumented = True
            except Exception:
                # Best-effort — a missing optional dep must not prevent the app from starting.
                logger.warning("startup.metrics_setup_failed")

    # Main API router (prefixed with /api).
    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "assemblix_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
