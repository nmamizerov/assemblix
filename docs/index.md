# Assemblix

**Assemblix** is a visual AI agent / workflow automation platform. You build workflows as
directed graphs of nodes on a [React Flow](https://reactflow.dev/) canvas, then execute and
monitor them. Workflows can call multiple LLM providers and run end to end with
observability built in.

## What you can build

Workflows are directed graphs of typed nodes:

| Node | Purpose |
| --- | --- |
| `START` | Entry point of the graph |
| `AGENT` | An LLM agent loop (calls a provider, can use tools) |
| `CONDITION` | Branch on a CEL expression |
| `SET_VARIABLE` | Write values into the run's variable scope |
| `HTTP_REQUEST` | Call an external HTTP endpoint |
| `STICKER` | Annotation / note on the canvas (no execution effect) |
| `END` | Terminal node of the graph |

New node types can be added without a DB migration — see the workflow nodes guide,
[CONTRIBUTING_NODES.md](CONTRIBUTING_NODES.md).

## Features

- **Multiple LLM providers** — OpenAI, Gemini, DeepSeek (via LiteLLM).
- **Multi-tenancy** — organizations and projects, scoped credentials and resources.
- **Knowledge bases (RAG)** — upload documents and ground agents on them.
- **Credentials** — encrypted-at-rest secrets for providers and integrations.
- **Chat sessions** — conversational runs against your workflows.
- **Observability** — Prometheus metrics, health/readiness probes, in-flight execution
  view. See [observability](observability.md).

## Architecture at a glance

Two independently-built apps:

- **Backend** — FastAPI (Python 3.13, async SQLAlchemy, PostgreSQL).
- **Frontend** — React 19 + Vite (TypeScript, Feature-Sliced Design).

The frontend talks to the backend over REST; the API is the source of truth for the node
graph schema. Read the full breakdown in [architecture](architecture.md).

## Get going

- [Getting started](getting-started.md) — fastest path to a running dev stack.
- [Self-hosting](self-hosting.md) — production Docker Compose, queue tier, ops.
- [Configuration](configuration.md) — the root `.env` reference.
- [Troubleshooting](troubleshooting.md) — common issues and fixes.

## License

Source-available under **MIT + Commons Clause** — free to use, modify, and self-host; you
may not sell it or offer it as a paid hosted/managed service. A small set of files
(payments / acquiring) is under a separate **Enterprise license** and is disabled by
default for self-hosting (`BILLING_ENABLED=false`). See the `LICENSE.md` and `LICENSE_EE.md`
files in the repository.
