# Get started

Everything you need to run a self-hosted Assemblix instance. We start with the
**dependencies**, then walk through the **example Docker Compose files** we ship so you can
pick the one that matches your setup.

## Dependencies

For the Docker path (recommended) the only thing you install on the host is:

- **[Docker](https://docs.docker.com/get-docker/)** with **Compose v2** (`docker compose`).
- **openssl** or **python3** — only to generate the two required secrets (below). No full
  host Python is needed.

Everything else is pinned inside the images — you do **not** install these on the host:

| Runtime | Version | Where |
| --- | --- | --- |
| PostgreSQL | 16 | `postgres:16-alpine` |
| Python | 3.13 | API image (`uv`) |
| Node | 22 | web build |
| Redis | 7 | `redis:7-alpine` (optional queue tier) |

> **Running natively, without Docker?** You additionally need Python 3.13 +
> [uv](https://docs.astral.sh/uv/) and Node 22 + [yarn](https://yarnpkg.com/). See
> [Running natively](#running-natively-without-docker) below.

## 1. Clone and configure

All configuration lives in a **single `.env` at the repo root** — the backend, the frontend
build, and Docker Compose all read it.

```bash
git clone https://github.com/nmamizerov/assemblix.git
cd assemblix
cp .env.example .env
```

## 2. Set the two required secrets

The backend **fails fast on startup** without a valid `JWT_SECRET_KEY` (min 32 chars) and
`ENCRYPTION_KEY` (a Fernet key). Generate them and paste the values into `.env`:

```bash
# JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Only `VITE_`-prefixed vars are bundled into the frontend, so these secrets never reach the
browser.

> In a hurry? `cp .env.example.quick .env` gives you a file with only those two secrets to
> fill; everything else uses a working default. Or run `make setup` (`./setup.sh`) to
> generate the secrets, write `.env`, and bring the stack up in one command.

## 3. Pick an example Compose file

We ship three ready-made Compose files at the repo root — run all of them **from the repo
root**. Pick the one that matches what you're doing.

### `docker-compose.yml` — self-host production (default)

The lean self-host stack: `postgres + migrate + api + web + docs`. Migrations run
automatically (a one-shot `migrate` service applies Alembic, then the API waits for it — so
migrations never race across replicas). No Redis or worker.

```bash
docker compose up -d --build      # or: make prod
```

| Service | URL / detail |
| --- | --- |
| web | http://localhost:8080 |
| api | http://localhost:8000 |
| docs | served under `/docs` (nginx proxies the MkDocs container) |
| db | internal network only (not published) |

Ports come from `WEB_PORT` (default 8080) and `API_PORT` (default 8000); the DB is reachable
only over the internal Docker network via the `postgres` hostname.

### `docker-compose.dev.yml` — development (live reload)

The full dev stack with hot reload — Postgres, Redis, the API (`fastapi dev`), the web app
(Vite HMR), and the Arq worker. Source is bind-mounted; the API applies migrations on start.

```bash
docker compose -f docker-compose.dev.yml up --build      # or: make dev
```

| Service | URL / detail |
| --- | --- |
| web | http://localhost:5173 (Vite HMR) |
| api | http://localhost:8000 (`fastapi dev` reload) |
| postgres | `127.0.0.1:5412` (localhost only) |

Want just one service (e.g. only the DB, and run the apps another way)?

```bash
docker compose -f docker-compose.dev.yml up postgres
```

### `docker-compose.app.yml` — app tier only (bring your own Postgres)

The web + api + docs tier with **no bundled database** — you point it at a managed Postgres
(Neon, Supabase, RDS…). Designed for PaaS platforms like Coolify/Portainer, which surface
the required vars in their UI. The API migrates on startup; only `web` is exposed publicly.
Required: `DATABASE_URL`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`.

### Optional: Redis + worker queue tier

Off by default. To enable distributed execution (the API enqueues, an Arq worker runs the
graph), set in `.env`, then `docker compose up -d`:

```bash
COMPOSE_PROFILES=queue
REDIS_URL=redis://redis:6379/0
EXECUTION_QUEUE_ENABLED=true
```

Scale workers with `WORKER_REPLICAS` (each runs up to `WORKER_MAX_JOBS` concurrent jobs).
For heavier deployments add the **scale tier** (`COMPOSE_PROFILES=queue,scale`), which puts a
transaction-mode PgBouncer in front of Postgres so real DB connections are capped instead of
growing with `replicas × pool_size`:

```bash
COMPOSE_PROFILES=queue,scale
DB_TARGET_HOST=pgbouncer          # route api/worker through the pooler
DB_TARGET_PORT=6432               # PgBouncer port, NOT the host-published POSTGRES_PORT
DB_DISABLE_STATEMENT_CACHE=true   # asyncpg-safe behind transaction pooling
```

Migrations always connect to Postgres directly — DDL is unsafe through a transaction-mode
pooler.

### `make` shortcuts

The root `Makefile` wraps the common commands:

```bash
make setup       # one-command bootstrap: generate secrets, write .env, start the stack
make dev         # docker-compose.dev.yml up (live reload)
make prod        # docker-compose.yml up -d --build
make down        # stop the dev stack
make logs        # follow dev logs
```

## Essential configuration

The full `.env` has many knobs, but these are the ones that matter for a first self-host:

| Variable | Default | Description |
| --- | --- | --- |
| `JWT_SECRET_KEY` | *(required)* | JWT signing key, **min 32 chars**. Backend fails fast without it. |
| `ENCRYPTION_KEY` | *(required)* | Fernet key for encrypting stored credentials. Fails fast without it. |
| `COMPOSE_PROFILES` | *(empty)* | Empty = core only; `queue` = Redis + worker; `queue,scale` = + PgBouncer. |
| `API_PORT` / `WEB_PORT` | `8000` / `8080` | Host ports for the API and web app. |
| `POSTGRES_PASSWORD` | `assemblix` | **Change for any non-local deployment.** |
| `DATABASE_URL` | `…@localhost:5412/assemblix` | HOST value; compose overrides it to the `postgres` host. Set this yourself for `docker-compose.app.yml`. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,…` | Comma-separated frontend origin(s), **no trailing slash**. |
| `SYSTEM_OPENAI_API_KEY` / `SYSTEM_GEMINI_API_KEY` / `SYSTEM_DEEPSEEK_API_KEY` | *(blank)* | System LLM keys; blank = self-host bring-your-own-key per credential. |
| `SYSTEM_ELEVENLABS_API_KEY` | *(blank)* | Voice output (TTS); optional. |
| `HTTP_NODE_ALLOW_INTERNAL` | `false` | SSRF opt-out for the HTTP-request node. Leave `false` unless you understand the risk. |
| `BILLING_ENABLED` | `false` | Enterprise billing; keep `false` for self-hosting. |

Every variable is documented with comments in `.env.example`.

## Running natively (without Docker)

The same root `.env` is read by host processes. Start just the database in Docker, then run
each app on the host:

```bash
docker compose -f docker-compose.dev.yml up -d postgres

# Backend (from assemblix-app-api/) — reads ../.env, applies migrations, serves :8000
cd assemblix-app-api
uv sync
uv run alembic upgrade head
make dev

# Frontend (from assemblix-app-web/) — reads ../.env, serves :5173, proxies /api → :8000
cd assemblix-app-web
yarn install
yarn dev
```

## Common issues

**The app won't start (fail-fast on secrets).** `JWT_SECRET_KEY` must be present and at least
32 characters; `ENCRYPTION_KEY` must be a valid Fernet key. Regenerate them (see step 2) and
put them in the root `.env`.

**Database connection errors.** `DATABASE_URL` in `.env` is a *host* value; inside Compose it
is overridden to the in-network `postgres` host, so you don't edit it for the standard flows.
Running natively? Make sure Postgres is up and `DATABASE_URL` points at the host-published
port (`5412`).

**HTTP-request node is blocked.** The HTTP node has SSRF protection and refuses internal /
private addresses by default. Only set `HTTP_NODE_ALLOW_INTERNAL=true` if you understand the
risk.

**Queue features don't work.** Distributed execution, Redis-backed debug events, and
checkpointing require the queue tier. A blank `REDIS_URL` means single-process, Postgres-only
operation — enable the `queue` profile (above).

**`/payments` returns 404.** Billing is an Enterprise feature, disabled by default
(`BILLING_ENABLED=false`), so its routes return `404`. This is expected for the
source-available build.

**Port conflicts.** Change `API_PORT`, `WEB_PORT`, or `POSTGRES_PORT` in `.env`. The dev web
port (`5173`) and worker metrics port (`METRICS_PORT`, default `9000`) may also conflict.

**Common operations.**

```bash
docker compose ps                 # status
docker compose logs -f api        # follow API logs
docker compose down               # stop (keeps the DB volume)
docker compose down -v            # stop and delete the DB volume
```
