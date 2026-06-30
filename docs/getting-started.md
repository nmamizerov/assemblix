# Getting started

The fastest path to a running Assemblix dev stack with live reload.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose v2 (`docker compose`).

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
browser. See [configuration](configuration.md) for the full variable reference.

> In a hurry? `cp .env.example.quick .env` gives you a file with only those two secrets to
> fill; everything else uses a working default.

## 3. Start the development stack

Run from the repo root. This brings up the whole stack with live reload — Postgres, Redis,
the API (`fastapi dev`), the web app (Vite HMR), and the Arq worker (`--watch`):

```bash
docker compose -f docker-compose.dev.yml up --build
```

(The root `Makefile` wraps this as `make dev`.)

## 4. Open the apps

| Service | URL / detail |
| --- | --- |
| web | http://localhost:5173 (Vite HMR) |
| api | http://localhost:8000 (`fastapi dev` reload) |
| postgres | `127.0.0.1:5412` (localhost only) |
| redis | internal network only |
| worker | Arq, `--watch` autoreload |

Want just one service (e.g. only the DB, and run the apps another way)?

```bash
docker compose -f docker-compose.dev.yml up postgres
```

## Next steps

- Deploy a production instance — [self-hosting](self-hosting.md).
- Understand how the pieces fit — [architecture](architecture.md).
- Tune behavior via env vars — [configuration](configuration.md).
