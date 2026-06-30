# Self-hosting

Run a production Assemblix instance with Docker Compose. Run all compose commands **from the
repo root**. First complete [getting started](getting-started.md) steps 1–2 (clone + the two
required secrets), then continue here.

## Production stack (lean default)

The default self-host stack is `postgres + migrate + api + web`. Migrations run automatically
(the one-shot `migrate` service applies Alembic, then the API waits for it to finish before
starting — so migrations never race across replicas). No Redis or worker is started.

```bash
docker compose up -d --build
```

(The root `Makefile` wraps this as `make prod`.)

| Service | URL / detail |
| --- | --- |
| web | http://localhost:8080 |
| api | http://localhost:8000 |
| db | internal network only (not published) |

Port mappings come from `WEB_PORT` (default 8080), `API_PORT` (default 8000), and the DB is
reachable only over the internal Docker network via the `postgres` hostname.

## Optional: Redis + worker queue tier

Off by default. To enable distributed execution (the API enqueues, an Arq worker runs the
graph), set in `.env`:

```bash
COMPOSE_PROFILES=queue
REDIS_URL=redis://redis:6379/0
EXECUTION_QUEUE_ENABLED=true
```

then `docker compose up -d`. The `redis` and `worker` services sit behind the `queue`
Compose profile; core services have no profile, so they always start. Scale workers with
`WORKER_REPLICAS` (each runs up to `WORKER_MAX_JOBS` concurrent jobs); set
`WORKER_METRICS_ENABLED=false` when running more than one replica on a single host to avoid
`METRICS_PORT` bind collisions.

## Optional: scale tier (PgBouncer)

Once you run several api/worker replicas, put a transaction-mode PgBouncer in front of
Postgres so real DB connections are capped instead of growing with `replicas × pool_size`.
Set in `.env`:

```bash
COMPOSE_PROFILES=queue,scale
DB_TARGET_HOST=pgbouncer          # route api/worker through the pooler
DB_TARGET_PORT=6432               # PgBouncer port, NOT the host-published POSTGRES_PORT
DB_DISABLE_STATEMENT_CACHE=true   # asyncpg-safe behind transaction pooling
```

Migrations always connect to Postgres directly (DDL and prepared statements are unsafe
through a transaction-mode pooler).

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

Native development needs Python 3.13 + [uv](https://docs.astral.sh/uv/) and
Node 22 + [yarn](https://yarnpkg.com/).

## Common operations

```bash
docker compose ps                 # status
docker compose logs -f api        # follow API logs
docker compose down               # stop (keeps the DB volume)
docker compose down -v            # stop and delete the DB volume
```

## Security reminders

- **Change `POSTGRES_PASSWORD`** for any non-local deployment.
- Keep secrets out of git — generate `JWT_SECRET_KEY` and `ENCRYPTION_KEY` at deploy time
  and store them as deployment secrets, never commit a real `.env`.
- Set `CORS_ALLOWED_ORIGINS` to your real frontend origin(s).
- The HTTP-request node blocks internal targets by default (SSRF protection); only set
  `HTTP_NODE_ALLOW_INTERNAL=true` if you understand the risk.

See [configuration](configuration.md) for the full variable reference and
[troubleshooting](troubleshooting.md) if something does not come up.
