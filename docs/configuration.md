# Configuration

All configuration lives in a **single `.env` at the repo root**. The backend, the frontend
build (`VITE_*` vars), and Docker Compose all read it. Copy it from `.env.example` and fill
in the two required secrets.

> **Only `VITE_`-prefixed vars are bundled into the frontend** and reach the browser. Every
> other variable stays server-side.

## Required secrets

| Variable | Default | Description |
| --- | --- | --- |
| `JWT_SECRET_KEY` | *(required)* | Signing key for JWTs. **Min 32 chars.** Backend fails fast without it. |
| `ENCRYPTION_KEY` | *(required)* | Fernet key for encrypting stored credentials. Backend fails fast without it. |

Generate them:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"                       # JWT_SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY
```

## Compose & services

| Variable | Default | Description |
| --- | --- | --- |
| `COMPOSE_PROFILES` | *(empty)* | Service profiles; empty = core only, `queue` = Redis + worker, add `scale` = PgBouncer |
| `API_PORT` | `8000` | Host port for the API |
| `WEB_PORT` | `8080` | Host port for the web app (prod) |

## Database

| Variable | Default | Description |
| --- | --- | --- |
| `POSTGRES_USER` | `assemblix` | Postgres user |
| `POSTGRES_PASSWORD` | `assemblix` | Postgres password — **CHANGE for non-local** |
| `POSTGRES_DB` | `assemblix` | Postgres database name |
| `POSTGRES_PORT` | `5412` | Host-published DB port |
| `DATABASE_URL` | `postgresql://assemblix:assemblix@localhost:5412/assemblix` | HOST value; compose overrides it to point at the `postgres` host |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Extra connections beyond the pool size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a pooled connection |
| `DB_DISABLE_STATEMENT_CACHE` | `false` | Set `true` only behind a transaction-mode pooler |
| `DB_TARGET_HOST` | `postgres` | DB host api/worker connect to; `pgbouncer` on the scale tier |
| `DB_TARGET_PORT` | `5432` | DB port; `6432` for PgBouncer |
| `PGBOUNCER_MAX_DB_CONNECTIONS` | `50` | Real backend connections PgBouncer opens to Postgres |
| `PGBOUNCER_MAX_CLIENT_CONN` | `1000` | Client connections PgBouncer accepts |
| `PGBOUNCER_DEFAULT_POOL_SIZE` | `25` | PgBouncer default pool size |

## Auth & security

| Variable | Default | Description |
| --- | --- | --- |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Access token lifetime (24h) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed origins, no trailing slash |
| `HTTP_NODE_ALLOW_INTERNAL` | `false` | SSRF opt-out for the HTTP-request node |
| `LOGIN_RATE_LIMIT_PER_5MIN` | `10` | Login attempts allowed per 5 minutes |

## Execution limits

| Variable | Default | Description |
| --- | --- | --- |
| `WORKFLOW_EXECUTION_TIMEOUT_SECONDS` | `1800` | Max wall-clock time for a workflow run |
| `CEL_EVALUATION_TIMEOUT_SECONDS` | `5` | Max time to evaluate a CEL condition |
| `TASK_TIMEOUT_SECONDS` | `60` | Per-task timeout |
| `GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS` | `30` | Grace period on shutdown |

## Knowledge bases (RAG)

| Variable | Default | Description |
| --- | --- | --- |
| `KB_MAX_UPLOAD_BYTES` | `26214400` | Max upload size (25 MB) |
| `KB_MAX_PDF_PAGES` | `500` | Max pages parsed per PDF |
| `KB_PDF_PARSE_TIMEOUT_SECONDS` | `30` | PDF parse timeout |

## LLM providers

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_API_BASE_URL` | `https://api.openai.com/v1` | OpenAI API base URL |
| `GEMINI_API_BASE_URL` | *(blank)* | Gemini API base URL |
| `SYSTEM_OPENAI_API_KEY` | *(blank)* | System OpenAI key; blank = self-host BYO-key |
| `SYSTEM_GEMINI_API_KEY` | *(blank)* | System Gemini key |
| `SYSTEM_DEEPSEEK_API_KEY` | *(blank)* | System DeepSeek key |
| `TAVILY_API_KEY` | *(blank)* | Tavily key for web search |

## OAuth

| Variable | Default | Description |
| --- | --- | --- |
| `GOOGLE_OAUTH_CLIENT_ID` | *(blank)* | Google OAuth client ID (blank = provider hidden) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | *(blank)* | Google OAuth client secret |
| `GITHUB_OAUTH_CLIENT_ID` | *(blank)* | GitHub OAuth client ID (blank = provider hidden) |
| `GITHUB_OAUTH_CLIENT_SECRET` | *(blank)* | GitHub OAuth client secret |

## Queue, Redis & metrics

| Variable | Default | Description |
| --- | --- | --- |
| `REDIS_URL` | *(blank)* | Blank = single-process Postgres-only; queue tier: `redis://redis:6379/0` |
| `EXECUTION_QUEUE_ENABLED` | `false` | Enqueue executions to the worker |
| `DEBUG_EVENTS_USE_REDIS` | `false` | Stream debug events via Redis |
| `EXECUTION_CHECKPOINTING_ENABLED` | `false` | Persist execution checkpoints |
| `METRICS_ENABLED` | `true` | Expose Prometheus `/metrics` |
| `METRICS_PORT` | `9000` | Worker metrics scrape port |
| `WORKER_MAX_JOBS` | `10` | Concurrent jobs per worker process |
| `WORKER_REPLICAS` | `1` | Number of worker processes |
| `WORKER_METRICS_ENABLED` | `true` | Expose worker metrics (set `false` for >1 replica per host) |
| `WEB_CONCURRENCY` | `1` | API worker processes |
| `PROMETHEUS_MULTIPROC_DIR` | *(empty)* | Dir for multiprocess Prometheus metrics |
| `ORG_MAX_CONCURRENCY` | `0` | Per-org concurrency cap (0 = unlimited) |
| `PROVIDER_MAX_CONCURRENCY` | `0` | Per-provider concurrency cap (0 = unlimited) |
| `CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS` | `30` | Time to wait for a concurrency slot |

## Misc

| Variable | Default | Description |
| --- | --- | --- |
| `HOST_URL` | `http://localhost:8000` | Public base URL of the API |
| `TELEGRAM_API_BASE_URL` | *(blank)* | Blank = `api.telegram.org` |

## Billing (Enterprise — disabled by default)

These are gated behind the Enterprise license and off for self-hosting.

| Variable | Default | Description |
| --- | --- | --- |
| `BILLING_ENABLED` | `false` | When `false`, the `/payments` router is not mounted |
| `PAYMENT_PROVIDER` | `paddle` | Active payment provider |
| `PADDLE_API_KEY` | *(blank)* | Paddle API key |
| `PADDLE_WEBHOOK_SECRET` | *(blank)* | Paddle webhook secret |
| `PADDLE_ENVIRONMENT` | `sandbox` | Paddle environment |
| `PADDLE_PRICE_STARTER` | *(blank)* | Paddle price ID — Starter |
| `PADDLE_PRICE_PRO` | *(blank)* | Paddle price ID — Pro |
| `CREDIT_VALUE_USD` | `0.0001` | USD value of one credit |
| `CREDIT_MARGIN_PERCENT` | `10` | Margin applied to credit cost |
| `REQUEST_FEE_USD` | `0.0001` | Per-request fee |

## Frontend (`VITE_*`)

These are the only variables compiled into the browser bundle.

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api` | API base path the frontend calls |
| `VITE_APP_VERSION` | `1.0.0` | Displayed app version |
| `VITE_LANGS` | `ru,en` | Available languages |
| `VITE_DEFAULT_LANGUAGE` | `ru` | Default language |
| `VITE_SUPPORTED_LANGUAGES` | `ru,en` | Supported languages |
| `VITE_GOOGLE_CLIENT_ID` | *(blank)* | Google OAuth client ID (frontend) |
| `VITE_GITHUB_CLIENT_ID` | *(blank)* | GitHub OAuth client ID (frontend) |
| `VITE_YANDEX_CLIENT_ID` | *(blank)* | Yandex OAuth client ID (frontend) |
| `VITE_PADDLE_CLIENT_TOKEN` | *(blank)* | Paddle client token (frontend) |
| `VITE_PADDLE_ENVIRONMENT` | `production` | Paddle environment (frontend) |
