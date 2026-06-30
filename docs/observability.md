# Observability

Assemblix exposes health/readiness probes, Prometheus metrics, and an in-flight execution
view, plus structured logging.

## Probes

### `GET /health`

Liveness probe. No I/O — always returns `200` while the process is up. Use it for container
liveness checks.

### `GET /ready`

Readiness probe. Runs `SELECT 1` against the database and, when Redis is configured, pings
Redis. Returns `503` if any dependency is down. Use it for load-balancer readiness and
deployment gating.

## Metrics

### `GET /metrics`

Prometheus text exposition, gated by `METRICS_ENABLED` (default `true`). The API serves its
metrics here; the **worker process exposes its own scrape server** on `METRICS_PORT`
(default `9000`).

Metric families cover:

- **Workflow executions** — total count and a duration histogram.
- **Node steps** — counted by node type and status.
- **LLM usage** — tokens and cost.
- **Queue depth** — pending work in the queue tier.
- **In-progress nodes** — a gauge of nodes currently executing.

> When running more than one worker replica on a single host, set
> `WORKER_METRICS_ENABLED=false` to avoid `METRICS_PORT` bind collisions. For multiprocess
> API metrics, set `PROMETHEUS_MULTIPROC_DIR`.

A minimal Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: assemblix-api
    static_configs:
      - targets: ["api:8000"]
    metrics_path: /metrics
  - job_name: assemblix-worker
    static_configs:
      - targets: ["worker:9000"]
```

## In-flight executions

### `GET /api/executions/in-flight`

Returns executions currently in `RUNNING` / `QUEUED` state for the authenticated project
(scope-guarded). Useful for dashboards and for spotting stuck runs.

## Structured logging

The backend logs with [structlog](https://www.structlog.org/), emitting structured
(key/value) log lines that are easy to ship to a log aggregator and correlate with the
metrics above.

See [configuration](configuration.md) for `METRICS_ENABLED`, `METRICS_PORT`, and related
worker variables.
