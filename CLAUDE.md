# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Assemblix** — a visual AI agent / workflow automation platform. Users build workflows
as directed graphs of nodes (START, AGENT, CONDITION, SET_VARIABLE, HTTP_REQUEST,
STICKER, END) on a React Flow canvas, then execute and monitor them. Workflows can call
multiple LLM providers (OpenAI, Gemini, DeepSeek). The platform supports
multi-tenancy (organizations, projects), knowledge bases (RAG), credentials, chat
sessions, and — in the commercial build — billing/credits and payments.

This repository is the **open-source / source-available build** of a product that also
ships as a hosted commercial service. Enterprise-only concerns (billing, payments) are
gated behind feature flags and are off by default for self-hosting — see Licensing below.

## Monorepo layout

This is a single repo holding two independently-built applications:

```
assemblix/
  assemblix-app-api/    — FastAPI backend (Python 3.13, async SQLAlchemy, PostgreSQL)
  assemblix-app-web/    — React 19 + Vite frontend (TypeScript, Feature-Sliced Design)
  .github/workflows/    — CI (backend pipeline + repo-wide secret scan)
  docs/                 — PUBLIC documentation site (MkDocs) + node-authoring guide
  internal-docs/        — internal, NOT published: superpowers plans/specs, dev notes
```

> **`docs/` is published** — it is the source for the public MkDocs site served at
> `/docs`. Put **only** user-facing product/self-hosting docs there. **Internal**
> material (superpowers plans & specs, maintainer notes) goes in **`internal-docs/`**,
> never `docs/`. In particular, override the superpowers `writing-plans` default:
> save plans to `internal-docs/superpowers/plans/…` and specs to
> `internal-docs/superpowers/specs/…` (NOT `docs/superpowers/…`). `mkdocs.yml`'s
> `exclude_docs` is a backstop, but keep internal files out of `docs/` in the first place.

**Each app has its own `CLAUDE.md` with the detail you need before working in it** — read
the relevant one first; this file is only the umbrella:

- [assemblix-app-api/CLAUDE.md](assemblix-app-api/CLAUDE.md) — backend architecture,
  commands, layering rules, the "add a new entity" checklist.
- [assemblix-app-web/CLAUDE.md](assemblix-app-web/CLAUDE.md) — frontend FSD layers,
  slice structure, RTK Query, i18n conventions.

The two apps are **separate toolchains** (uv/pytest vs npm/vite) — run commands from
inside the respective directory, not the repo root.

## How the two halves connect

- The frontend talks to the backend over a REST API. In dev, Vite proxies `/api/`
  requests to the backend at `http://localhost:8000` (see `assemblix-app-web/vite.config.ts`).
- The API is the source of truth for the node graph schema; the frontend canvas
  (React Flow / `@xyflow/react`) produces the nodes+edges JSON the backend executes.
  When adding or changing a node type, **both sides must change** — the backend node
  handler/registry and the frontend node UI.
- DTOs are camelCase on the wire: the backend auto-converts snake_case ↔ camelCase via
  `DTOModel` aliasing, so frontend types stay camelCase.

## Configuration: one `.env` at the repo root

There is a **single `.env` at the repo root** — the source of truth for the backend,
the frontend build (`VITE_*` vars), and Docker Compose. Copy it from
[.env.example](.env.example) and fill in the two required secrets:

```bash
cp .env.example .env                        # then fill JWT_SECRET_KEY + ENCRYPTION_KEY
#   …or the bare-minimum prod start (just the two required secrets):
cp .env.example.quick .env
```

The backend **fails fast on startup** without a valid `JWT_SECRET_KEY` and
`ENCRYPTION_KEY` — generation commands are in the comments of `.env.example`. Only
`VITE_`-prefixed vars are bundled into the frontend, so the secrets in this shared file
never reach the browser. `DATABASE_URL`/`REDIS_URL` hold _host_ values; the compose files
override them to the in-network `postgres`/`redis` service hosts.

## Running the whole stack — Docker Compose

Two root compose files; **run them from the repo root**. Service toggling uses Compose
profiles via `COMPOSE_PROFILES` in `.env` (core services are always on; the Redis + Arq
worker `queue` tier is opt-in). The root `Makefile` wraps the common commands: `make dev`,
`make prod`, `make down`, `make logs`, and `make check` (gates of both apps).

```bash
# DEV — full stack with live reload (the day-to-day workflow):
#   postgres + redis + api (fastapi dev) + web (vite HMR) + worker (arq --watch)
docker compose -f docker-compose.dev.yml up --build      # web → :5173, api → :8000
#   …or just one service, e.g. only Postgres (run the app another way):
docker compose -f docker-compose.dev.yml up postgres

# PROD — lean self-host default: postgres + migrate + api + web (no Redis/worker)
docker compose up -d --build                             # web → :8080, api → :8000
#   enable the queue tier: set in .env → COMPOSE_PROFILES=queue,
#   REDIS_URL=redis://redis:6379/0, EXECUTION_QUEUE_ENABLED=true, then `up -d`.
```

### Running natively on the host (no Docker)

The same root `.env` is read by host processes:

```bash
# infra only
docker compose -f docker-compose.dev.yml up postgres
# backend (from assemblix-app-api/) — reads ../.env
make dev                                    # → :8000
# frontend (from assemblix-app-web/) — reads ../.env
yarn install && yarn dev                    # Vite → :5173, proxies /api → :8000
```

## CI and quality gates

CI spans both apps. The **backend** pipeline ([.github/workflows/ci.yml](.github/workflows/ci.yml))
runs lint/ruff, mypy, bandit SAST, and pytest+coverage. The **frontend** pipeline
([.github/workflows/web-ci.yml](.github/workflows/web-ci.yml)) runs vitest unit tests and
the TypeScript build (type-check) as hard gates, and eslint as a non-blocking step
(pre-existing react-hooks violations are being cleaned up). A **repo-wide gitleaks secret scan runs on every PR**
regardless of which app changed. Each pipeline is path-filtered, so a frontend-only PR
skips the Python jobs (and vice-versa) but is still secret-scanned. The docs site is built
and deployed by [.github/workflows/docs.yml](.github/workflows/docs.yml).

To mirror CI locally for the backend: `cd assemblix-app-api && make check` (or `make check`
from the repo root, which runs both apps' gates).

Secret-scanning config is `.gitleaks.toml` at the repo root. Since this repo is public,
never commit real secrets — generate ephemeral ones at runtime (as the Makefile and CI do).

## Git & release workflow (read before create new changes)

Branch off `main`; keep PRs focused; never push or open PRs unprompted. **Commit/PR-title
messages must follow [Conventional Commits](https://www.conventionalcommits.org)**
(`feat:`, `fix:`, `feat!:`, …) — they drive versioning automatically. Releases are managed
by **release-please**: do **not** hand-edit version numbers
(`assemblix-app-api/pyproject.toml`, `assemblix-app-web/package.json`), `CHANGELOG.md`, or
git tags. Merging Conventional-Commit PRs into `main` keeps a release PR open that bumps the
single repo version in lockstep and regenerates the changelog; merging it cuts the `vX.Y.Z`
tag + GitHub Release. **Full rules: [docs/git-workflow.md](docs/git-workflow.md)** (also in
[CONTRIBUTING.md](CONTRIBUTING.md) for contributors).

## Licensing model (important when adding/moving code)

Source-available: **MIT + Commons Clause** — free to use, modify, and self-host; you may
**not** sell it or offer it as a paid hosted/managed service. A subset of files (notably
**payments / Paddle billing**) is under a separate **commercial (Enterprise) license**
and is feature-flagged off for self-host (`BILLING_ENABLED=false` → the `/payments` router
is not mounted). Keep enterprise-licensed and OSS code clearly separated; don't entangle
billing/payment logic into core execution paths. EE files carry an
`SPDX-License-Identifier: LicenseRef-Assemblix-EE` header. See [LICENSE.md](LICENSE.md) /
[LICENSE_EE.md](LICENSE_EE.md), and the per-package READMEs.
