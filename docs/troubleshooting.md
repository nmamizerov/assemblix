# Troubleshooting

Common issues when running Assemblix and how to fix them. See
[configuration](configuration.md) for every variable mentioned here.

## The app won't start (fail-fast on secrets)

The backend **fails fast on startup** if the two required secrets are missing or invalid:

- `JWT_SECRET_KEY` must be present and **at least 32 characters**.
- `ENCRYPTION_KEY` must be a valid **Fernet** key.

Regenerate them and put them in the root `.env`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"                       # JWT_SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY
```

## Database connection errors

`DATABASE_URL` in `.env` is a **host** value (defaults to `localhost:5412`). Inside Docker
Compose it is overridden to the in-network `postgres` host — you do not need to edit it for
the standard compose flows.

- Running **natively**? Make sure Postgres is up (`docker compose -f docker-compose.dev.yml
  up -d postgres`) and `DATABASE_URL` points at the host-published port (`5412` by default).
- On the **scale tier**, api/worker connect through PgBouncer via `DB_TARGET_HOST=pgbouncer`
  / `DB_TARGET_PORT=6432`; also set `DB_DISABLE_STATEMENT_CACHE=true`.

## HTTP-request node is blocked

The HTTP-request node has **SSRF protection** and refuses to call internal/private
addresses by default. If you intentionally need it to reach an internal service, set
`HTTP_NODE_ALLOW_INTERNAL=true` — only do this if you understand the risk.

## `/payments` returns 404

Billing is an Enterprise feature and is **disabled by default** for self-hosting:
`BILLING_ENABLED=false` means the `/payments` router is not mounted, so its routes return
`404`. This is expected for the source-available build.

## Queue features don't work

Distributed execution, Redis-backed debug events, and checkpointing require the queue tier.
A blank `REDIS_URL` means single-process, Postgres-only operation. To enable the worker:

```bash
COMPOSE_PROFILES=queue
REDIS_URL=redis://redis:6379/0
EXECUTION_QUEUE_ENABLED=true
```

then `docker compose up -d`. See [self-hosting](self-hosting.md).

## Port conflicts

If a port is already in use, change the relevant variable in `.env`:

- `API_PORT` (default `8000`)
- `WEB_PORT` (default `8080`, prod)
- `POSTGRES_PORT` (default `5412`, host-published DB port)

The dev web port (`5173`) and the worker metrics port (`METRICS_PORT`, default `9000`) may
also conflict.

## CORS errors in the browser

Set `CORS_ALLOWED_ORIGINS` to the exact origin(s) your frontend is served from —
comma-separated, with **no trailing slash** (e.g. `https://app.example.com`). The default
covers local dev (`http://localhost:5173,http://localhost:3000`).

## Still stuck?

- Check service status and logs: `docker compose ps` and `docker compose logs -f api`.
- Confirm dependencies are healthy with the readiness probe — see
  [observability](observability.md).
