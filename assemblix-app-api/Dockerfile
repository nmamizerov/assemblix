# syntax=docker/dockerfile:1
# ============================================================================
# Assemblix API image. Multi-stage; the same image backs the api, worker, and
# migrate compose services (the command is overridden per service).
#
#   target: prod  -> uvicorn (runtime deps only)
#   target: dev   -> fastapi dev with autoreload (includes dev tooling)
# ============================================================================

# --- common base: uv + Python 3.13 -----------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Entrypoint optionally applies DB migrations (RUN_MIGRATIONS=true) before exec.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# --- production image -------------------------------------------------------
FROM base AS prod
# Install runtime deps first (cached unless the lockfile changes), then source.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . .
EXPOSE 8000
# Binaries resolve from /app/.venv/bin (on PATH) — no `uv run` needed at runtime.
# Shell form so ${WEB_CONCURRENCY} expands at runtime (uvicorn --workers). Scale the
# API tier by raising WEB_CONCURRENCY or running more replicas. The worker service
# overrides this command with `arq ... WorkerSettings` in compose.
CMD ["sh", "-c", "uvicorn assemblix_api.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1}"]

# --- development image (autoreload) ----------------------------------------
FROM base AS dev
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
COPY . .
EXPOSE 8000
CMD ["fastapi", "dev", "assemblix_api/main.py", "--host", "0.0.0.0"]
