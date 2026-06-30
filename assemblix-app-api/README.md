# Assemblix API

FastAPI backend for **Assemblix** — a visual AI agent / workflow automation platform.
Python 3.13, async SQLAlchemy, PostgreSQL. This package owns the node-graph schema and the
workflow execution engine; the [web app](../assemblix-app-web) renders the canvas.

> New here? Start with the **[root README](../README.md)** for the one-command quickstart
> that runs the whole stack.

## Run it

Configuration comes from the **single `.env` at the repo root** (`../.env`) — see the root
README. From this directory, for native host development:

```bash
uv sync
uv run alembic upgrade head     # apply migrations
make dev                        # fastapi dev → http://localhost:8000
```

Postgres for native dev (from the repo root):
`docker compose -f docker-compose.dev.yml up -d postgres`.

API docs once running: Swagger at `/docs`, ReDoc at `/redoc`. Liveness `/health`,
readiness `/ready`, Prometheus `/metrics`.

## Architecture

4-layer: **API → Service → Repository → Model**, with Pydantic DTOs between layers. The
execution engine (`WorkflowExecutor`, `GraphNavigator`, `AgentOrchestrator`) lives under
`assemblix_api/execution/`; node handlers under `assemblix_api/nodes/`. The authoritative
guide for layering rules, the "add a new entity" checklist, and the test harness is
**[CLAUDE.md](CLAUDE.md)**.

## Tests & quality gates

```bash
pytest tests/unit/      # unit tests
make check              # lint (ruff), types (mypy), SAST (bandit), tests + coverage
```

## License

Source-available: **MIT + Commons Clause** ([../LICENSE.md](../LICENSE.md)). Files marked
`LicenseRef-Assemblix-EE` (payments) are under the separate
[Enterprise license](../LICENSE_EE.md). See [../NOTICE](../NOTICE) for attributions.
