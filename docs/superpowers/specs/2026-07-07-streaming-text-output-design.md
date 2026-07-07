# Streaming text output (token-level, debug-first) — Design

- **Date:** 2026-07-07
- **Status:** Approved design (pre-implementation)
- **Sub-project:** 2a of 3 in the "conversational voice + avatars" initiative
- **Author:** design session (brainstorming)

## 1. Context and the larger initiative

Assemblix is a visual workflow/agent platform. A chat turn is a workflow execution; the
final reply is produced at the END node. Today execution is **fully buffered**: the AGENT
node runs `pydantic_ai.Agent.run(...)` and returns one completed value; the production path
is synchronous-with-polling (`task=true` → `execution_id` → poll `GET /workflows/task/{id}`).
The only live signal is **step-level** SSE (`step_start` / `step_complete`) in debug mode.

The larger initiative decomposes into three sequential sub-projects:

| # | Sub-project | Depends on |
|---|-------------|------------|
| 1 | Voice output on the END node (ElevenLabs, non-streaming) — **done** | the `external/voice/` seam |
| **2a** | **Streaming of text tokens (this spec)** | #1 |
| 2b | Streaming of audio chunks (streaming TTS via the reserved `capability:"realtime"` slot) | #2a |
| 3 | AI avatars (real-time lip-sync) | #2b |

Note the split: the memory framed phase 2 as "token-level LLM streaming **+** audio-chunk
transport." We deliberately split it into **2a (text tokens)** and **2b (audio chunks)** so
each is a single, reviewable implementation plan. This spec is **2a only**.

**Guiding principle:** build the streaming *mechanism* (per-execution event log + delta
events + subscribe-by-cursor SSE) as a general capability, but ship exactly one consumer —
the **debug runner** with a "streaming" toggle — so the whole path is exercisable end-to-end.
Non-streaming behavior must remain byte-for-byte identical to today.

## 2. Scope

### In scope (2a)

- A per-node **`stream: bool`** flag on the AGENT node (which agents may stream to the user).
- A per-request **`stream: bool`** flag on `ExecuteWorkflowRequest` (does *this run* stream).
  Works on **any run**, not only debug.
- Token-level streaming of an agent's **free-form text** output through a new
  `STREAM_DELTA` event on the existing debug event bus.
- A **per-execution ordered event buffer** (sequence-numbered event log) with two backends
  mirroring the existing bus: in-memory deque (self-host/inline) and Redis Stream (queued).
- A new **`GET /api/executions/{id}/stream`** SSE endpoint that replays the buffer from a
  cursor (`Last-Event-ID`) and then tails live until `execution_complete`/`error`.
- Extending `AgentRunner` with a streaming path via pydantic-ai's streaming API and teaching
  the in-process litellm shim to handle `stream=True`.
- A **frontend debug-runner toggle** ("streaming") that consumes the two-request transport
  and renders deltas live.
- Extending the **LLM mock seam** (`tests/plugins/llm.py`) to arm streamed chunk responses.

### Out of scope (explicitly deferred)

- **Audio-chunk / streaming TTS** — sub-project 2b. END voice output continues to work
  exactly as in phase 1 (synthesize the whole final text at the END node). Text deltas and
  END-voice are orthogonal in 2a.
- **A production, non-debug chat streaming UI** — the *mechanism* works for any run, but the
  only UI consumer we build is the debug runner. Wiring the customer-facing chat surface is a
  later spec.
- **Streaming of structured (`json_object`) agent output** — buffered and parsed as today.
- **Persisting deltas or partial text** — deltas are ephemeral; only the existing final
  output (step + END) is persisted.
- **AI avatars** — sub-project 3.

## 3. Key decisions

### 3.1 Three-gate emission rule

A `STREAM_DELTA` is emitted for an agent node **iff all three hold**:

1. `request.stream is True` (the run asked to stream), **and**
2. the AGENT node's `stream is True` (the author marked this agent streamable), **and**
3. the node's resolved `response_format == "text"` (i.e. `parse_json is False`).

This dissolves the "detect the last agent node" problem entirely: the *author* declares
intent per node, so no fragile static/`CONDITION`-dependent terminal detection is needed.
`json_object` + `stream` is a config mistake → `AgentNode.validate_config()` emits a canvas
warning and the node runs buffered (no deltas), never an error.

### 3.2 Two flags at two levels

- **Per-node** `AgentNodeConfig.stream: bool = False` — eligibility.
- **Per-request** `ExecuteWorkflowRequest.stream: bool = False` — activation for this run.

Both are needed: the per-node flag prevents an intermediate agent from streaming even when
the run is streaming; the per-request flag turns streaming on/off for a run without editing
the graph.

### 3.3 The event bus becomes an ordered, replayable log

Today `DebugEventManager` fans out `DebugEvent`s over an in-process `asyncio.Queue` or Redis
Pub/Sub, with **no replay** (a late subscriber misses earlier events; only the
`wait_for_client` gate mitigates this for the single-request debug endpoint).

For the two-request subscribe model we add a **monotonic `seq`** to *every* event on an
execution and retain them in a per-execution **buffer-log**:

- **In-memory backend** (no Redis): a bounded `deque` per execution, appended on each emit;
  subscribers read from their own cursor over the shared buffer.
- **Redis backend** (queued tier / `DEBUG_EVENTS_USE_REDIS`): a **Redis Stream** per
  execution (`XADD` on emit, `XRANGE`/`XREAD` from cursor). Stream entry ids are the natural
  cursor.

The buffer is **ephemeral**: TTL'd, dropped a short grace period after
`execution_complete`/`error`. Nothing here touches the database.

### 3.4 The buffer, not `wait_for_client`, closes the start/subscribe race

With `execute(task=true)`, the run starts in the background before the client subscribes.
The executor **must not block** waiting for a subscriber. Instead it runs freely and appends
to the buffer; a late or reconnecting subscriber catches up by replaying from its cursor.
`wait_for_client` remains only for the legacy single-request `/execute/debug` path (see 3.8).

### 3.5 Streaming in `AgentRunner` — the core change

`AgentRunner.run` gains an optional `on_delta: Callable[[str], Awaitable[None]] | None`:

- **`on_delta is None`** (default): unchanged — `agent.run(...)`, one buffered result.
- **`on_delta` provided**: use pydantic-ai's streaming API (`agent.iter()` / `run_stream`),
  iterate text-part deltas, and `await on_delta(chunk)` for each. After the stream drains,
  produce the **same** `AgentExecutionResult` contract (content / `parsed_content` /
  `metadata{tokens, cost, tool_calls_count, effective_model}` / `tool_executions`) from the
  streamed result's `usage()` and `all_messages()`. Billing, `step_complete`, and history are
  unchanged.

`AgentNode.execute` decides whether to pass a real `on_delta` (three-gate satisfied) or
`None`, and builds the callback closed over the current `step_number` / `node_id` so deltas
are correctly tagged.

**Risk / spike task #1 (first in the plan):** confirm the exact streaming API of the
installed `pydantic-ai` and that streaming flows correctly through the custom
`LiteLLMModel(OpenAIChatModel)` shim — including that `usage()`/`all_messages()`/tool
executions are still available after a streamed run. This de-risks everything downstream.

### 3.6 The litellm shim learns `stream=True`

`_Completions.create` (`external/llm/litellm_model.py:54`) currently always aggregates one
`ChatCompletion` via `resp.model_dump()`. For streaming, pydantic-ai's `OpenAIChatModel`
calls `client.chat.completions.create(stream=True)` and expects an async-iterable of
`ChatCompletionChunk`. The shim will branch on `stream`:

- **`stream` falsy** → today's path unchanged.
- **`stream` truthy** → return an async-iterator adapter over
  `litellm.acompletion(..., stream=True)` that yields chunk objects shaped like
  `ChatCompletionChunk` (re-validated from each litellm chunk's `model_dump()`), and supports
  whatever close/`async with` protocol pydantic-ai uses on the stream (confirmed in spike #1).

### 3.7 New event type and schema

- `DebugEventType.STREAM_DELTA = "stream_delta"`.
- `StreamDeltaEventData(node_id: str, step_number: int, seq: int, delta: str)`.
- `DebugEvent` carries `seq` (added to the base event) so replay/cursoring works uniformly
  for all event types, not just deltas.
- No artificial coalescing in 2a — deltas are emitted as the streaming API yields them.
  (Server-side coalescing is a later optimization if network chattiness warrants it.)

### 3.8 Debug transport: unify, but preserve today's behavior exactly

The debug runner moves to the two-request transport
(`execute(task=true, is_debug=true, stream=?)` → `GET /executions/{id}/stream`). Hard
constraint: **when the streaming toggle is off, the run behaves identically to today** — the
frontend does not send `stream`, no `STREAM_DELTA` events are produced, and the observed
event set (`step_start` / `step_complete` / `execution_complete` / `error`) is unchanged. The
legacy `POST /execute/debug` endpoint keeps working as-is; folding it fully onto the buffered
bus is a follow-up cleanup, not a 2a requirement, and must not regress non-streaming debug.

### 3.9 Persistence and scrub

Deltas never reach the database. The final agent text and END output are persisted through
the existing step / execution-output path, unchanged. On reconnect the client replays from
the ephemeral buffer; if the buffer has expired, it falls back to `GET /workflows/task/{id}`
for the final result. This mirrors phase 1's "live-only, scrubbed-before-persist" philosophy.

### 3.10 Bus activation broadened

Today the bus is created only for `is_debug` runs. In 2a it is created when
**`is_debug OR stream`**, so a non-debug run with `stream=true` also gets an event log and is
subscribable. Billing and rate-limits for such runs are unchanged from any normal run.

## 4. Architecture and data flow

```
Client (debug runner)
  │  1) POST /api/workflows/{id}/execute { task:true, is_debug:true, stream:true, input }
  ▼
executions.py ──► dispatch (inline asyncio.create_task  OR  arq worker)
  │                         creates event buffer when (is_debug OR stream)
  │  ◄── 202 { execution_id }
  │
  │  2) GET /api/executions/{execution_id}/stream   (SSE, Last-Event-ID: <seq>)
  ▼
event_generator ──► buffer.replay(from=cursor) ─► live tail
        ▲                                              │
        │  seq'd events (step_start / STREAM_DELTA / step_complete / execution_complete)
        │                                              │
WorkflowExecutor ─► NodeRunner ─► AgentNode.execute ─► AgentRunner.run(on_delta=…)
                                                          │  pydantic-ai stream
                                                          ▼
                                                 LiteLLMModel shim (stream=True)
                                                          ▼
                                                 litellm.acompletion(stream=True)
```

- **Inline / self-host:** executor and SSE subscriber share the process; buffer is the
  in-memory deque.
- **Queued:** worker emits to the Redis Stream; the API process's SSE subscriber reads it
  (`XREAD` from cursor). Consistent with "Redis optional for self-host".
- **Parallel engine (`DagScheduler`):** two streamable agents can run concurrently; deltas
  interleave on the bus but each carries `node_id`/`step_number`, so the client demuxes by
  node. Multiple subscribers to one execution each hold their own cursor.

## 5. Components and interfaces (unit boundaries)

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `AgentNodeConfig.stream` (`schemas/node.py`) | Per-node eligibility + `validate_config` warning on `json_object`+`stream` | — |
| `ExecuteWorkflowRequest.stream` (`dto/requests/execution.py`) | Per-run activation | — |
| `AgentRunner.run(on_delta)` (`execution/agent_runner.py`) | Streaming vs buffered path; unchanged result contract | pydantic-ai streaming, shim |
| `LiteLLMModel` shim (`external/llm/litellm_model.py`) | `stream=True` → chunk async-iterator | litellm |
| `StreamDeltaEventData` + `seq` (`schemas/debug_events.py`) | New event type + ordering | — |
| Event buffer (in-memory deque / Redis Stream) | Ordered, replayable, TTL'd per-execution log | Redis (optional) |
| `DebugEventManager` extension | `emit_stream_delta`, seq assignment, buffer append | buffer |
| `GET /executions/{id}/stream` (`api/rest/executions.py`) | Subscribe-by-id SSE with cursor replay + live tail | buffer, event manager |
| Debug-runner toggle + delta rendering (frontend) | "streaming" checkbox, EventSource, demux by node_id, reconnect by Last-Event-ID | SSE endpoint |
| `mock_llm` streaming (`tests/plugins/llm.py`) | Arm streamed chunk responses for tests | — |

## 6. Error handling

- **LLM error mid-stream:** partial deltas already delivered stay; the executor emits the
  normal `error` event and the execution goes `FAILED`, exactly as a non-streaming failure.
- **Timeout:** the existing `total_timeout` / `AgentRunTimeoutError` bounding still applies to
  the streamed run (do not retry — tools may have run).
- **Client disconnect / reconnect:** reconnect with `Last-Event-ID` replays missed events
  from the buffer; buffer-expired → fall back to `GET /workflows/task/{id}`.
- **Buffer overflow:** bounded buffer drops oldest; a subscriber whose cursor fell off the
  buffer receives a gap marker and should fall back to the poll endpoint for the final result.

## 7. Configuration (new settings, with defaults)

- `STREAM_BUFFER_TTL_SECONDS` (starting default `600`) — how long an execution's buffer/Stream
  is retained after completion.
- `STREAM_BUFFER_MAX_EVENTS` (starting default `2000`) — in-memory deque / Redis Stream `MAXLEN`.
- Streaming reuses the existing `DEBUG_EVENTS_USE_REDIS` toggle to pick the backend; no new
  Redis requirement for self-host.

(Starting defaults are chosen now so implementation is unblocked; §9 flags tuning them as an
open item once real delta volumes are observed.)

## 8. Testing strategy

Per backend rule **§0**, the concrete test cases for this new feature **come from the user**
and will be collected at the start of the implementation plan, before any test or code. The
harness support this spec must add:

- Extend `tests/plugins/llm.py` so `mock_llm` can arm a **streamed** response (an async
  iterator of chunk dicts) returned when `stream=True`, alongside the existing buffered
  `set_response` / `queue_responses`.
- Unit coverage themes (final cases from the user): three-gate emission (each gate off →
  buffered), `seq` monotonicity and cursor replay, in-memory vs Redis buffer parity,
  reconnect-by-cursor, `json_object`+`stream` warning + buffered fallback, mid-stream error →
  `FAILED`, and non-streaming debug behaving byte-for-byte as before.
- Verify e2e via `curl`/`httpie` against `GET /executions/{id}/stream`, plus a browser
  dogfood of the debug-runner toggle.

## 9. Open items to confirm during planning

- Exact pydantic-ai streaming API + shim behavior (spike #1) — may adjust 3.5/3.6 wording.
- Whether the in-memory buffer fan-out to multiple subscribers needs an explicit
  per-execution subscriber registry or a simple cursor-over-deque suffices.
- Final buffer TTL / max-events values.
- Whether `GET /executions/{id}/stream` should require `is_debug`/`stream` to have been set at
  dispatch (it should: only such runs have a buffer) and how to respond otherwise (404 vs a
  one-shot final-state event).
