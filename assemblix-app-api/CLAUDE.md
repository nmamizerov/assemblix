# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Assemblix API — a FastAPI backend for a visual workflow automation platform. Users build workflows as directed graphs of nodes (LLM agents, conditions, HTTP requests, etc.) and execute them via API. The system supports multi-tenancy with organizations, projects, billing/credits, and OAuth.

## Commands

```bash
# Activate venv (required before any command)
source .venv/bin/activate

# Run dev server
fastapi dev assemblix_api/main.py

# Run all unit tests
pytest tests/unit/

# Run a single test file
pytest tests/unit/test_graph_navigator.py

# Run a single test
pytest tests/unit/test_graph_navigator.py::test_name -v

# Install packages (always use uv, never pip)
uv add <package>

# Create migration (never run alembic autogenerate directly — use the script)
./makemigrations.sh "migration message"

# Create and apply migration
./makemigrations.sh "migration message" --upgrade

# Apply migrations
alembic upgrade head

# Start PostgreSQL (port 5412 -> 5432). Compose lives at the repo root now;
# run from there. `up postgres` starts only the DB for host-native dev.
#   (cd .. && docker compose -f docker-compose.dev.yml up postgres)
```

Config (incl. `DATABASE_URL`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`) is read from the
**single repo-root `.env`** (`../.env`) — see the root README/CLAUDE.md. Copy it once with
`cp ../.env.example ../.env` and fill the two required secrets.

## Architecture

**4-layer architecture**: API → Service → Repository → Model

- `assemblix_api/api/rest/` — FastAPI routers. HTTP contract only, no business logic. Uses `Depends()` for DI.
- `assemblix_api/services/` — Business logic. Receives repositories via `__init__`. Inherits `BaseService[Model, Repository]`.
- `assemblix_api/database/repositories/` — DB operations only. Inherits `BaseRepository[ModelType]`. No business logic, no HTTP concepts.
- `assemblix_api/database/models/` — SQLAlchemy ORM models. Inherit `UUIDMixin`, `TimestampMixin`, `Base`.
- `assemblix_api/dto/` — Pydantic DTOs (`requests/` and `responses/`). All inherit `DTOModel` (auto camelCase ↔ snake_case via `alias_generator`).
- `assemblix_api/dependencies.py` — All DI wiring: `get_db_session` → `get_*_repository` → `get_*_service`. Register new entities here.

### Workflow Execution Engine

- `assemblix_api/nodes/` — Node types (start, end, agent, condition, http_request, set_variable). Registered in `NodeRegistry` singleton at startup.
- `assemblix_api/execution/` — `WorkflowExecutor` orchestrates execution, `GraphNavigator` traverses the DAG, `AgentOrchestrator` handles LLM agent loops, `ToolExecutor` runs tools.
- `assemblix_api/core/cel_evaluator.py` — CEL expression evaluator for condition nodes.
- `assemblix_api/core/node_registry.py` — Singleton registry mapping node types to handler classes.

### Other Key Modules

- `assemblix_api/billing/` — Credit system, rate limiting, subscription plans.
- `assemblix_api/oauth/` — OAuth provider registry (Google).
- `assemblix_api/core/encryption.py` — Encryption service for credentials storage.
- `assemblix_api/core/settings.py` — `Settings` class via pydantic-settings, cached with `@lru_cache`.

## Key Rules

- **Always use DTOs between layers** — never pass raw `dict` between API/Service/Repository layers.
- **No business logic in routers or repositories.**
- **No SQLAlchemy queries in services.**
- **No `HTTPException` in repositories.**
- **Write tests first, then implementation** (TDD approach, always 2 stages).
- **When writing ANY test, follow [rules/writing-tests.md](rules/writing-tests.md)** — the
  single source of truth for the test harness, fixtures, layers (unit/integration/external),
  the LLM mock seam, and the mandatory **AAA (Arrange–Act–Assert)** pattern.
- **When developing a NEW feature, the test cases come from the user — request and describe
  them BEFORE writing tests or implementation** (see rules/writing-tests.md §0). Do not
  invent test cases on the user's behalf.
- **Never create Alembic migrations manually** — only write the command for the migration.
- **Install packages only via `uv add`**, not pip.
- **Activate `.venv`** before running any Python command or script.

## Tech Stack

- Python 3.13, FastAPI, SQLAlchemy (async with asyncpg), Alembic
- PostgreSQL, Pydantic/pydantic-settings
- LLM integration via LiteLLM (OpenAI, Gemini, GigaChat, DeepSeek)
- Auth: JWT + API keys (prefixed `sk_`), Google OAuth
- Payments: Paddle (Merchant of Record)
- Package management: uv
- Deployment: Nixpacks

## Observability

- **`GET /health`** — liveness probe; no I/O, always 200 while the process is up.
- **`GET /ready`** — readiness probe; runs `SELECT 1` against the DB and, when Redis is
  configured, pings Redis. Returns 503 if any dependency is down.
- **`GET /metrics`** — Prometheus text exposition. Gated by `METRICS_ENABLED` (default
  `true`). The worker process exposes its own scrape server on `METRICS_PORT` (default
  `9000`). Metric families are defined in `assemblix_api/core/metrics.py` and cover:
  workflow executions (total + duration histogram), node steps (by type + status), LLM
  tokens and cost, queue depth, and in-progress node gauge.
- **`GET /api/executions/in-flight`** — returns executions currently in RUNNING/QUEUED
  state for the authenticated project (scope-guarded).

## Extending Nodes (Node SDK)

Nodes register by **string type** using the `@register_node("type")` decorator (defined
in `assemblix_api/core/node_registry.py`). Each node class can declare a `descriptor()`
classmethod returning a `NodeDescriptor` — the data-driven shape that drives the
frontend panel for plugin/delay nodes; existing built-in nodes keep their custom React
widgets. Out-of-tree packages are auto-discovered at startup via the entry-point group
`assemblix.nodes` (see `assemblix_api/core/node_loader.py`). The `node_type` column in
`execution_steps` is a plain `VARCHAR(100)`, so new node types need no DB migration.
Unknown types round-trip safely through the `GenericNode` schema fallback rather than
failing validation. For a worked example and packaging guide see
[CONTRIBUTING_NODES.md](../docs/CONTRIBUTING_NODES.md) in the repo's docs/.

## Adding a New Entity Checklist

1. `database/models/new_entity.py` — model with `UUIDMixin, TimestampMixin, Base`
2. `database/repositories/new_entity_repository.py` — inherits `BaseRepository[NewEntity]`
3. `dto/requests/new_entity.py` — request DTOs inheriting `DTOModel`
4. `dto/responses/new_entity.py` — response DTOs inheriting `DTOModel`
5. `services/new_entity_service.py` — business logic
6. `api/rest/new_entity.py` — router
7. `dependencies.py` — register `get_new_entity_repository` and `get_new_entity_service`
8. Migration command: `alembic revision --autogenerate -m "add new_entity"`
