# Streaming text output (token-level, debug-first) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream an agent's free-form text output token-by-token to a subscribing client over SSE, exercised through the debug runner, without changing non-streaming behavior.

**Architecture:** `AgentRunner` gains a streaming path via pydantic-ai's `agent.run(..., event_stream_handler=...)` (identical result contract, full tool loop) that pushes text deltas through an `on_delta` callback threaded down `WorkflowExecutor → NodeRunner → NodeInput → AgentNode → AgentRunner`. Deltas become a new `STREAM_DELTA` event on `DebugEventManager`, which is extended into a sequence-numbered, replayable per-execution buffer (in-memory deque; Redis Stream for the cross-process/queued case). A new `GET /api/executions/{id}/stream` SSE endpoint replays the buffer from a `Last-Event-ID` cursor and tails live.

**Tech Stack:** Python 3.13, FastAPI, pydantic-ai-slim 1.107.0, litellm 1.80.13, openai 2.42.0, async SQLAlchemy, Redis (optional), React 19 + Vite (frontend consumer).

## Global Constraints

- **Activate the venv** before any Python command: `source .venv/bin/activate` (from `assemblix-app-api/`).
- **Package management via `uv add` only**, never pip.
- **TDD, two stages**: write the failing test first, watch it fail, then the minimal implementation. Follow `assemblix-app-api/rules/writing-tests.md` (AAA, the `mock_llm` seam patched at `assemblix_api.external.llm.litellm_model.litellm.acompletion`).
- **Test cases are fixed** (collected from the user, rule §0): the confirmed set A1–A4, B5–B7, C8–C13, D14–D15, E16–E17 from the design's §8. Do not invent new behaviors; each task implements a subset of these.
- **No Alembic migration** — `stream` on the AGENT node lives in the workflow's node JSON, `stream` on the request is request-only, `stream_enabled` on `ExecutionContext` is in-memory. There is no new DB column.
- **DTOs between layers**; camelCase on the wire via `DTOModel` (so `ExecuteWorkflowRequest.stream` is `stream` in JSON; `AgentNodeConfig.stream` likewise).
- **Comments/docstrings in English**, minimal and only for non-trivial logic.
- **Conventional Commits** for every commit (`feat:`, `test:`, `refactor:`…). Never bump versions/CHANGELOG by hand.
- **Scope:** text tokens only. No audio-chunk streaming, no production non-debug chat UI, no `json_object` streaming, no delta persistence. END voice output is untouched.

## File Structure

**Backend — create:**
- `assemblix_api/execution/stream_buffer.py` — the sequence-numbered replayable buffer: `InMemoryStreamBuffer` and `RedisStreamBuffer`, behind a small `StreamBuffer` protocol.
- `tests/unit/test_stream_buffer.py`, `tests/unit/test_litellm_stream_shim.py`, `tests/unit/test_agent_runner_streaming.py`, `tests/unit/test_agent_node_stream_gate.py`, `tests/unit/test_debug_event_manager_stream.py`, `tests/integration/test_execution_stream_endpoint.py`, `tests/integration/test_streaming_e2e.py`.

**Backend — modify:**
- `assemblix_api/external/llm/litellm_model.py` — `_Completions.create` handles `stream=True` via a new `_StreamShim`.
- `assemblix_api/execution/agent_runner.py` — `run(..., on_delta=...)` streaming path.
- `assemblix_api/schemas/debug_events.py` — `STREAM_DELTA`, `StreamDeltaEventData`, `seq` on `DebugEvent`.
- `assemblix_api/execution/debug_event_manager.py` — seq assignment, buffer wiring, `emit_stream_delta`, `is_streaming`, `subscribe`.
- `assemblix_api/schemas/execution.py` — `ExecutionContext.stream_enabled`, `NodeInput.on_delta`.
- `assemblix_api/execution/node_runner.py` — build the `on_delta` sink in `run`.
- `assemblix_api/execution/workflow_executor.py` — pass `node_id`/`step_number` to `NodeRunner.run`; set `stream_enabled` on the context; create the stream buffer when `is_debug OR stream`.
- `assemblix_api/nodes/agent_node.py` — read `node_input.on_delta`, apply the format gate, pass to `AgentRunner`; `validate_config` warning.
- `assemblix_api/schemas/node.py` — `AgentNodeConfig.stream`.
- `assemblix_api/dto/requests/execution.py` — `ExecuteWorkflowRequest.stream`.
- `assemblix_api/api/rest/executions.py` — the `GET /{execution_id}/stream` endpoint; thread `stream` through dispatch.
- `assemblix_api/core/settings.py` — `stream_buffer_ttl_seconds`, `stream_buffer_max_events`.
- `tests/plugins/llm.py` — streamed-chunk arming on `mock_llm`.

**Frontend — modify** (exact component confirmed in Task 12 via grep):
- The debug-runner send control + its SSE consumer under `assemblix-app-web/src/`.

---

### Task 1: litellm shim learns `stream=True`

**Files:**
- Modify: `assemblix_api/external/llm/litellm_model.py:41-66`
- Test: `tests/unit/test_litellm_stream_shim.py`

**Interfaces:**
- Produces: `_Completions.create(**kwargs)` returns today's `ChatCompletion` when `stream` is falsy, and a `_StreamShim` (async-iterable of `ChatCompletionChunk`, supporting `async with` + `close()`) when `kwargs["stream"]` is truthy.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_litellm_stream_shim.py
import pytest
from openai.types.chat import ChatCompletionChunk

from assemblix_api.external.llm.litellm_model import _Completions, _StreamShim


class _FakeLiteLLMChunk:
    """Mimics litellm ModelResponseStream: a pydantic-ish object with model_dump()."""

    def __init__(self, content: str):
        self._content = content

    def model_dump(self, warnings: bool = True) -> dict:
        return {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"content": self._content}, "finish_reason": None}],
        }


class _FakeLiteLLMStream:
    def __init__(self, contents):
        self._it = iter(contents)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return _FakeLiteLLMChunk(next(self._it))
        except StopIteration:
            raise StopAsyncIteration


@pytest.mark.asyncio
async def test_stream_shim_yields_chatcompletionchunks_and_supports_context_manager(mocker):
    # Arrange
    async def _fake_acompletion(**kwargs):
        assert kwargs.get("stream") is True
        return _FakeLiteLLMStream(["Hel", "lo"])

    mocker.patch(
        "assemblix_api.external.llm.litellm_model.litellm.acompletion",
        side_effect=_fake_acompletion,
    )
    completions = _Completions(defaults={}, env_overrides={}, api_key_env_var=None, api_key=None)

    # Act
    stream = await completions.create(model="openai/gpt-4o", messages=[], stream=True)
    collected = []
    async with stream as s:
        async for chunk in s:
            collected.append(chunk)
    await stream.close()

    # Assert
    assert isinstance(stream, _StreamShim)
    assert all(isinstance(c, ChatCompletionChunk) for c in collected)
    assert "".join(c.choices[0].delta.content or "" for c in collected) == "Hello"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_litellm_stream_shim.py -v`
Expected: FAIL — `ImportError: cannot import name '_StreamShim'`.

- [ ] **Step 3: Implement the shim streaming branch**

Add above `class _Chat` in `litellm_model.py`, and add the `ChatCompletionChunk` import next to `from openai.types.chat import ChatCompletion`:

```python
from openai.types.chat import ChatCompletion, ChatCompletionChunk


class _StreamShim:
    """Adapts a litellm streaming wrapper to what OpenAIChatModel consumes.

    OpenAIChatModel does `async with response:` then async-iterates the object and
    calls `await source.close()`. litellm's CustomStreamWrapper has none of those, so
    we wrap it: iterate its ModelResponseStream chunks and revalidate each into a real
    ChatCompletionChunk (attribute access is how pydantic-ai reads them).
    """

    def __init__(self, litellm_stream: Any):
        self._stream = litellm_stream

    async def __aenter__(self) -> "_StreamShim":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def __aiter__(self) -> "_StreamShim":
        return self

    async def __anext__(self) -> ChatCompletionChunk:
        chunk = await self._stream.__anext__()
        return ChatCompletionChunk.model_validate(chunk.model_dump(warnings=False))

    async def close(self) -> None:
        aclose = getattr(self._stream, "aclose", None)
        if aclose is not None:
            await aclose()
```

Then change `_Completions.create` to branch on `stream`:

```python
    async def create(self, **kwargs: Any) -> ChatCompletion | _StreamShim:
        for env_name, value in self._env_overrides.items():
            os.environ[env_name] = value
        if self._api_key_env_var and self._api_key:
            os.environ[self._api_key_env_var] = self._api_key

        merged = {**self._defaults, **_strip_sentinels(kwargs)}
        if merged.get("stream"):
            return _StreamShim(await litellm.acompletion(**merged))
        resp = await litellm.acompletion(**merged)
        return ChatCompletion.model_validate(resp.model_dump(warnings=False))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_litellm_stream_shim.py -v`
Expected: PASS.

- [ ] **Step 5: Run mypy on the changed file**

Run: `source .venv/bin/activate && mypy assemblix_api/external/llm/litellm_model.py`
Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
git add assemblix_api/external/llm/litellm_model.py tests/unit/test_litellm_stream_shim.py
git commit -m "feat(streaming): litellm shim supports stream=True via _StreamShim"
```

---

### Task 2: `mock_llm` can arm streamed chunk responses

**Files:**
- Modify: `tests/plugins/llm.py`
- Test: covered by its use in Task 3 (add a self-check assertion here).

**Interfaces:**
- Produces: `mock_llm.set_stream(chunks: list[str])` — arms `litellm.acompletion(**kwargs)` so that when `kwargs["stream"] is True` it returns an async iterator yielding objects with `.model_dump()` shaped like an OpenAI `chat.completion.chunk` (one chunk per string). Non-stream calls keep returning the existing buffered `_ModelResponse`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mock_llm_stream.py
import pytest


@pytest.mark.asyncio
async def test_mock_llm_set_stream_yields_chunks(mock_llm):
    # Arrange
    mock_llm.set_stream(["A", "B", "C"])
    import assemblix_api.external.llm.litellm_model as m

    # Act
    stream = await m.litellm.acompletion(model="openai/gpt-4o", messages=[], stream=True)
    contents = []
    async for chunk in stream:
        contents.append(chunk.model_dump()["choices"][0]["delta"]["content"])

    # Assert
    assert contents == ["A", "B", "C"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_mock_llm_stream.py -v`
Expected: FAIL — `AttributeError: 'LLMMock' object has no attribute 'set_stream'`.

- [ ] **Step 3: Extend the mock**

In `tests/plugins/llm.py`, add a streamed-chunk type and `set_stream`, and make the patched `_acompletion` branch on `stream`:

```python
class _StreamChunk:
    """Mimics litellm ModelResponseStream.model_dump() for one delta."""

    def __init__(self, content: str):
        self._content = content

    def model_dump(self, warnings: bool = True) -> dict:
        return {
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "mock-model",
            "choices": [{"index": 0, "delta": {"content": self._content}, "finish_reason": None}],
        }


class _AsyncChunkStream:
    def __init__(self, chunks):
        self._it = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return _StreamChunk(next(self._it))
        except StopIteration:
            raise StopAsyncIteration
```

Add to `LLMMock`:

```python
    def set_stream(self, chunks: list[str]) -> None:
        """Arm the next stream=True acompletion to yield these text deltas in order."""
        self._stream_chunks = list(chunks)
```

Initialise `self._stream_chunks: list[str] | None = None` in `__init__`, and in the `_acompletion` side-effect branch on stream:

```python
    async def _acompletion(*args, **kwargs):
        mock.call_count += 1
        mock.calls.append(kwargs)
        if kwargs.get("stream"):
            chunks = mock._stream_chunks if mock._stream_chunks is not None else []
            return _AsyncChunkStream(chunks)
        return mock._next_response()  # existing buffered path (keep as-is)
```

(Adapt `mock._next_response()` to whatever the current non-stream return expression is — do not change that path.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_mock_llm_stream.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/plugins/llm.py tests/unit/test_mock_llm_stream.py
git commit -m "test(streaming): mock_llm.set_stream arms streamed chunks"
```

---

### Task 3: `AgentRunner` streaming path (`on_delta` via `event_stream_handler`)

Covers **B5** (concat == content), **B6** (usage/cost intact), **B7** (tool-call agent streams only final text).

**Files:**
- Modify: `assemblix_api/execution/agent_runner.py:94-174`
- Test: `tests/unit/test_agent_runner_streaming.py`

**Interfaces:**
- Consumes: `mock_llm.set_stream(...)` (Task 2), `_StreamShim` (Task 1).
- Produces: `AgentRunner.run(..., on_delta: Callable[[str], Awaitable[None]] | None = None)`. When `on_delta` is given, deltas are emitted during the run; the returned `AgentExecutionResult` is unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_agent_runner_streaming.py
import pytest

from assemblix_api.execution.agent_runner import AgentRunner
from assemblix_api.external.llm.litellm_model import build_litellm_model


@pytest.mark.asyncio
async def test_run_streams_text_deltas_and_keeps_result_contract(mock_llm):
    # Arrange
    mock_llm.set_stream(["Hel", "lo ", "world"])
    model = build_litellm_model("openai", "gpt-4o", "sk-test")
    seen: list[str] = []

    async def on_delta(text: str) -> None:
        seen.append(text)

    # Act
    result = await AgentRunner().run(
        model=model,
        provider="openai",
        model_name="gpt-4o",
        instructions=None,
        conversation=[{"role": "user", "content": "hi"}],
        on_delta=on_delta,
    )

    # Assert — B5: concatenation of deltas equals the final content
    assert "".join(seen) == "Hello world"
    assert result.content == "Hello world"
    # B6: usage metadata still present
    assert "tokens_used" in result.metadata and "cost" in result.metadata
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_agent_runner_streaming.py -v`
Expected: FAIL — `TypeError: run() got an unexpected keyword argument 'on_delta'`.

- [ ] **Step 3: Implement the streaming path**

In `agent_runner.py`, add imports for the event types:

```python
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
```

Add the `on_delta` parameter to `run` and build the handler. Replace the `run_coro = agent.run(...)` block with:

```python
    async def run(
        self,
        *,
        model: Model,
        provider: str,
        model_name: str,
        instructions: str | None,
        conversation: list[dict],
        toolsets: list | None = None,
        parse_json: bool = False,
        model_settings: ModelSettings | None = None,
        total_timeout: float | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> AgentExecutionResult:
        history, prompt = to_pydantic_messages(conversation)

        agent: Agent = Agent(model, instructions=instructions, toolsets=toolsets or [])

        event_stream_handler = _make_text_delta_handler(on_delta) if on_delta else None

        run_coro = agent.run(
            prompt,
            message_history=history,
            model_settings=model_settings,
            event_stream_handler=event_stream_handler,
        )
        try:
            if total_timeout is not None:
                result = await asyncio.wait_for(run_coro, timeout=total_timeout)
            else:
                result = await run_coro
        except TimeoutError as exc:
            raise AgentRunTimeoutError(f"Agent run exceeded its {total_timeout}s budget") from exc
```

Everything after `result = ...` (content extraction, usage, tool_executions, return) stays exactly as it is today. Add the handler factory near the module's other helpers:

```python
def _make_text_delta_handler(on_delta: Callable[[str], Awaitable[None]]):
    """Build a pydantic-ai event_stream_handler that forwards ONLY assistant text.

    Fires once per model-request node (again after each tool round). The first chunk of a
    new text part arrives as PartStartEvent(TextPart) — must not be dropped — and the rest
    as PartDeltaEvent(TextPartDelta). Tool-call / thinking events are ignored.
    """

    async def handler(ctx, events) -> None:
        async for event in events:
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if event.part.content:
                    await on_delta(event.part.content)
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                await on_delta(event.delta.content_delta)

    return handler
```

Add `from collections.abc import Awaitable, Callable` to the imports.

- [ ] **Step 4: Run the test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_agent_runner_streaming.py -v`
Expected: PASS.

- [ ] **Step 5: Verify the non-stream path is unchanged**

Run: `source .venv/bin/activate && pytest tests/unit/ -k agent_runner -v`
Expected: PASS (existing AgentRunner tests still green — `on_delta` defaults to `None`).

- [ ] **Step 6: Commit**

```bash
git add assemblix_api/execution/agent_runner.py tests/unit/test_agent_runner_streaming.py
git commit -m "feat(streaming): AgentRunner streams text deltas via event_stream_handler"
```

---

### Task 4: `STREAM_DELTA` event type, data schema, and `seq`

**Files:**
- Modify: `assemblix_api/schemas/debug_events.py:11-24`
- Test: `tests/unit/test_debug_event_manager_stream.py` (schema part)

**Interfaces:**
- Produces: `DebugEventType.STREAM_DELTA = "stream_delta"`; `StreamDeltaEventData(node_id: str, step_number: int, delta: str)`; `DebugEvent.seq: int = 0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_debug_event_manager_stream.py
from uuid import uuid4
from datetime import datetime

from assemblix_api.schemas.debug_events import (
    DebugEvent,
    DebugEventType,
    StreamDeltaEventData,
)


def test_stream_delta_event_serializes_with_seq():
    # Arrange
    data = StreamDeltaEventData(node_id="agent-1", step_number=2, delta="Hi")
    event = DebugEvent(
        event_type=DebugEventType.STREAM_DELTA,
        execution_id=uuid4(),
        timestamp=datetime.now(),
        data=data.model_dump(),
        seq=7,
    )

    # Assert
    dumped = event.model_dump(mode="json")
    assert dumped["eventType"] == "stream_delta"
    assert dumped["seq"] == 7
    assert dumped["data"]["delta"] == "Hi"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_debug_event_manager_stream.py::test_stream_delta_event_serializes_with_seq -v`
Expected: FAIL — `AttributeError`/`ImportError` on `StreamDeltaEventData` and unexpected `seq`.

- [ ] **Step 3: Implement the schema**

In `debug_events.py` add the enum member, the `seq` field, and the data model:

```python
class DebugEventType(str, Enum):
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STREAM_DELTA = "stream_delta"
    EXECUTION_COMPLETE = "execution_complete"
    ERROR = "error"


class DebugEvent(DTOModel):
    """Debug-mode event streamed to the client in real time over SSE."""

    event_type: DebugEventType
    execution_id: UUID
    timestamp: datetime
    data: dict[str, Any]
    # Monotonic per-execution sequence number; the SSE `id:` and cursor for replay.
    seq: int = 0


class StreamDeltaEventData(DTOModel):
    node_id: str
    step_number: int
    delta: str
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_debug_event_manager_stream.py::test_stream_delta_event_serializes_with_seq -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/schemas/debug_events.py tests/unit/test_debug_event_manager_stream.py
git commit -m "feat(streaming): STREAM_DELTA event type + seq on DebugEvent"
```

---

### Task 5: In-memory stream buffer

Covers **C8** (seq monotonic), **C9** (cursor replay), **C10** (reconnect no loss/dupes), **C12** (multiple subscribers).

**Files:**
- Create: `assemblix_api/execution/stream_buffer.py`
- Test: `tests/unit/test_stream_buffer.py`

**Interfaces:**
- Produces:
  - `class InMemoryStreamBuffer` with:
    - `def open(self, execution_id: UUID) -> None`
    - `async def append(self, execution_id: UUID, event: DebugEvent) -> int` — assigns and returns the event's `seq` (mutates `event.seq`), stores it (bounded by `max_events`), wakes subscribers.
    - `async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]` — yields buffered events with `seq > after_seq`, then live ones, returning after an `EXECUTION_COMPLETE`/`ERROR` event.
    - `def is_open(self, execution_id: UUID) -> bool`
    - `def drop(self, execution_id: UUID) -> None`
  - Terminal event types constant `TERMINAL_EVENTS = {DebugEventType.EXECUTION_COMPLETE, DebugEventType.ERROR}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_stream_buffer.py
import asyncio
from datetime import datetime
from uuid import uuid4

import pytest

from assemblix_api.execution.stream_buffer import InMemoryStreamBuffer
from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType


def _ev(eid, kind=DebugEventType.STREAM_DELTA, delta="x"):
    return DebugEvent(
        event_type=kind, execution_id=eid, timestamp=datetime.now(),
        data={"delta": delta}, seq=0,
    )


@pytest.mark.asyncio
async def test_append_assigns_monotonic_seq():  # C8
    buf = InMemoryStreamBuffer(max_events=100)
    eid = uuid4()
    buf.open(eid)
    s1 = await buf.append(eid, _ev(eid))
    s2 = await buf.append(eid, _ev(eid))
    assert (s1, s2) == (1, 2)


@pytest.mark.asyncio
async def test_subscribe_replays_after_cursor_then_completes():  # C9 + C10
    buf = InMemoryStreamBuffer(max_events=100)
    eid = uuid4()
    buf.open(eid)
    await buf.append(eid, _ev(eid, delta="a"))          # seq 1
    await buf.append(eid, _ev(eid, delta="b"))          # seq 2
    await buf.append(eid, _ev(eid, DebugEventType.EXECUTION_COMPLETE))  # seq 3

    got = [e async for e in buf.subscribe(eid, after_seq=1)]
    assert [e.seq for e in got] == [2, 3]               # 1 was already seen; skipped


@pytest.mark.asyncio
async def test_two_subscribers_each_get_full_stream_from_their_cursor():  # C12
    buf = InMemoryStreamBuffer(max_events=100)
    eid = uuid4()
    buf.open(eid)

    async def collect(cursor):
        return [e.seq async for e in buf.subscribe(eid, after_seq=cursor)]

    task_a = asyncio.create_task(collect(0))
    task_b = asyncio.create_task(collect(0))
    await asyncio.sleep(0)  # let both subscribe
    await buf.append(eid, _ev(eid))                      # seq 1
    await buf.append(eid, _ev(eid, DebugEventType.EXECUTION_COMPLETE))  # seq 2
    assert await task_a == [1, 2]
    assert await task_b == [1, 2]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/test_stream_buffer.py -v`
Expected: FAIL — module `stream_buffer` does not exist.

- [ ] **Step 3: Implement `InMemoryStreamBuffer`**

```python
# assemblix_api/execution/stream_buffer.py
"""Sequence-numbered, replayable per-execution event buffer for SSE streaming.

Two backends: an in-memory deque (self-host / inline runs, subscriber and executor share
the process) and a Redis Stream (queued/cross-process runs). Both assign a monotonic `seq`
to every event so a late or reconnecting subscriber replays from a cursor. The buffer is
ephemeral — never persisted; dropped after a TTL past completion.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from uuid import UUID

from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType

TERMINAL_EVENTS = {DebugEventType.EXECUTION_COMPLETE, DebugEventType.ERROR}


class InMemoryStreamBuffer:
    """Retains events per execution and fans out live to any number of subscribers."""

    def __init__(self, max_events: int = 2000):
        self._max_events = max_events
        self._events: dict[UUID, deque[DebugEvent]] = {}
        self._seq: dict[UUID, int] = {}
        self._conds: dict[UUID, asyncio.Condition] = {}

    def open(self, execution_id: UUID) -> None:
        self._events.setdefault(execution_id, deque(maxlen=self._max_events))
        self._seq.setdefault(execution_id, 0)
        self._conds.setdefault(execution_id, asyncio.Condition())

    def is_open(self, execution_id: UUID) -> bool:
        return execution_id in self._events

    async def append(self, execution_id: UUID, event: DebugEvent) -> int:
        if execution_id not in self._events:
            self.open(execution_id)
        self._seq[execution_id] += 1
        event.seq = self._seq[execution_id]
        self._events[execution_id].append(event)
        cond = self._conds[execution_id]
        async with cond:
            cond.notify_all()
        return event.seq

    async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        if execution_id not in self._events:
            return
        cond = self._conds[execution_id]
        cursor = after_seq
        while True:
            pending = [e for e in list(self._events[execution_id]) if e.seq > cursor]
            for event in pending:
                cursor = event.seq
                yield event
                if event.event_type in TERMINAL_EVENTS:
                    return
            async with cond:
                # Re-check under the lock to avoid missing a notify between the scan and wait.
                if any(e.seq > cursor for e in self._events[execution_id]):
                    continue
                await cond.wait()

    def drop(self, execution_id: UUID) -> None:
        self._events.pop(execution_id, None)
        self._seq.pop(execution_id, None)
        self._conds.pop(execution_id, None)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/test_stream_buffer.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/execution/stream_buffer.py tests/unit/test_stream_buffer.py
git commit -m "feat(streaming): in-memory sequence-numbered replayable stream buffer"
```

---

### Task 6: Redis stream buffer backend + parity

Covers **C11** (in-memory ↔ Redis parity).

**Files:**
- Modify: `assemblix_api/execution/stream_buffer.py`
- Test: `tests/unit/test_stream_buffer.py` (add a parity test using a fake redis)

**Interfaces:**
- Produces: `class RedisStreamBuffer` with the same method surface as `InMemoryStreamBuffer` (`open`, `append`, `subscribe`, `is_open`, `drop`), backed by a Redis Stream key `stream:events:{execution_id}` (`XADD MAXLEN ~ max_events`, an INCR seq field, `XREAD BLOCK` for live tail).

- [ ] **Step 1: Write the failing parity test**

```python
# add to tests/unit/test_stream_buffer.py
from assemblix_api.execution.stream_buffer import RedisStreamBuffer
from tests.plugins.fakeredis import FakeRedis  # a minimal in-test async Redis Streams stub


@pytest.mark.asyncio
async def test_redis_buffer_replays_after_cursor_like_in_memory():  # C11
    redis = FakeRedis()
    buf = RedisStreamBuffer(redis, max_events=100)
    eid = uuid4()
    buf.open(eid)
    await buf.append(eid, _ev(eid, delta="a"))          # seq 1
    await buf.append(eid, _ev(eid, delta="b"))          # seq 2
    await buf.append(eid, _ev(eid, DebugEventType.EXECUTION_COMPLETE))  # seq 3

    got = [e async for e in buf.subscribe(eid, after_seq=1)]
    assert [e.seq for e in got] == [2, 3]
    assert got[0].data["delta"] == "b"
```

- [ ] **Step 2: Add the fake redis Streams stub, then run to verify it fails**

Create `tests/plugins/fakeredis.py` with a minimal async `xadd`/`xrange`/`xread`/`incr`/`expire` over in-memory lists (enough for the buffer's calls). Then:

Run: `source .venv/bin/activate && pytest tests/unit/test_stream_buffer.py -k redis -v`
Expected: FAIL — `RedisStreamBuffer` not defined.

- [ ] **Step 3: Implement `RedisStreamBuffer`**

```python
import json


class RedisStreamBuffer:
    """Cross-process buffer backed by a Redis Stream (one per execution)."""

    def __init__(self, redis, max_events: int = 2000):
        self._redis = redis
        self._max_events = max_events

    def _key(self, execution_id: UUID) -> str:
        return f"stream:events:{execution_id}"

    def open(self, execution_id: UUID) -> None:
        # No-op: the stream is created lazily by the first XADD.
        return None

    def is_open(self, execution_id: UUID) -> bool:
        return True  # existence is checked by the endpoint via has_events()

    async def append(self, execution_id: UUID, event: DebugEvent) -> int:
        seq = await self._redis.incr(f"stream:seq:{execution_id}")
        event.seq = seq
        await self._redis.xadd(
            self._key(execution_id),
            {"seq": seq, "payload": event.model_dump_json()},
            maxlen=self._max_events,
            approximate=True,
        )
        return seq

    async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        key = self._key(execution_id)
        last_id = "0-0"
        seen_terminal = False
        # Replay everything retained, filter by cursor.
        for entry_id, fields in await self._redis.xrange(key):
            last_id = entry_id
            event = DebugEvent.model_validate_json(fields["payload"])
            if event.seq > after_seq:
                yield event
                if event.event_type in TERMINAL_EVENTS:
                    return
        # Live tail.
        while not seen_terminal:
            resp = await self._redis.xread({key: last_id}, block=25_000, count=50)
            if not resp:
                continue  # keepalive tick handled by the endpoint
            for _stream, entries in resp:
                for entry_id, fields in entries:
                    last_id = entry_id
                    event = DebugEvent.model_validate_json(fields["payload"])
                    if event.seq > after_seq:
                        yield event
                        if event.event_type in TERMINAL_EVENTS:
                            return
```

- [ ] **Step 4: Run the parity test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_stream_buffer.py -v`
Expected: PASS (in-memory + redis parity).

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/execution/stream_buffer.py tests/unit/test_stream_buffer.py tests/plugins/fakeredis.py
git commit -m "feat(streaming): Redis Stream buffer backend with in-memory parity"
```

---

### Task 7: Wire the buffer into `DebugEventManager` + settings

**Files:**
- Modify: `assemblix_api/execution/debug_event_manager.py`
- Modify: `assemblix_api/core/settings.py` (add two settings)
- Test: `tests/unit/test_debug_event_manager_stream.py`

**Interfaces:**
- Consumes: `InMemoryStreamBuffer` / `RedisStreamBuffer` (Tasks 5–6), `StreamDeltaEventData` (Task 4).
- Produces on `DebugEventManager`:
  - `async def emit_stream_delta(self, execution_id, *, step_number, node_id, delta) -> None`
  - `def is_streaming(self, execution_id) -> bool`
  - `async def subscribe(self, execution_id, after_seq) -> AsyncIterator[DebugEvent]`
  - `emit_event` now `await self._buffer.append(...)` (assigning `seq`) before the existing queue/redis dispatch, and `create_stream` calls `self._buffer.open(...)`.
- Settings: `stream_buffer_ttl_seconds: int = 600`, `stream_buffer_max_events: int = 2000`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/unit/test_debug_event_manager_stream.py
import pytest
from uuid import uuid4

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.debug_events import DebugEventType


@pytest.mark.asyncio
async def test_emit_stream_delta_is_buffered_and_subscribable():
    mgr = DebugEventManager()
    eid = uuid4()
    mgr.create_stream(eid)
    assert mgr.is_streaming(eid) is True

    await mgr.emit_stream_delta(eid, step_number=1, node_id="agent-1", delta="Hi")
    await mgr.emit_execution_complete(
        eid, status="completed", output={}, final_state={}, final_project_state={},
        total_steps=1, total_credits=__import__("decimal").Decimal("0"), duration_ms=1,
    )

    events = [e async for e in mgr.subscribe(eid, after_seq=0)]
    kinds = [e.event_type for e in events]
    assert DebugEventType.STREAM_DELTA in kinds
    assert events[0].seq == 1
    assert events[0].data["delta"] == "Hi"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_debug_event_manager_stream.py::test_emit_stream_delta_is_buffered_and_subscribable -v`
Expected: FAIL — `is_streaming`/`emit_stream_delta`/`subscribe` not defined.

- [ ] **Step 3: Extend `DebugEventManager`**

Add a buffer to `__init__` and wire it:

```python
    def __init__(
        self,
        redis_transport: RedisDebugEventTransport | None = None,
        buffer: "InMemoryStreamBuffer | RedisStreamBuffer | None" = None,
    ) -> None:
        self._streams: dict[UUID, asyncio.Queue] = {}
        self._client_ready: dict[UUID, asyncio.Event] = {}
        self._redis_transport = redis_transport
        from assemblix_api.execution.stream_buffer import InMemoryStreamBuffer

        self._buffer = buffer or InMemoryStreamBuffer()
```

In `create_stream`, after creating the queue, add `self._buffer.open(execution_id)`. In `emit_event`, assign seq via the buffer **first**, then do the existing dispatch:

```python
    async def emit_event(self, execution_id: UUID, event: DebugEvent) -> None:
        await self._buffer.append(execution_id, event)  # assigns event.seq + retains for replay
        if self._redis_transport is not None:
            await self._redis_transport.publish(execution_id, event.model_dump(mode="json"))
            return
        queue = self._streams.get(execution_id)
        if queue:
            await queue.put(event)
```

Add the three new methods:

```python
    def is_streaming(self, execution_id: UUID) -> bool:
        return self._buffer.is_open(execution_id)

    async def subscribe(self, execution_id: UUID, after_seq: int):
        async for event in self._buffer.subscribe(execution_id, after_seq):
            yield event

    async def emit_stream_delta(
        self, execution_id: UUID, *, step_number: int, node_id: str, delta: str
    ) -> None:
        from assemblix_api.schemas.debug_events import StreamDeltaEventData

        event_data = StreamDeltaEventData(node_id=node_id, step_number=step_number, delta=delta)
        event = DebugEvent(
            event_type=DebugEventType.STREAM_DELTA,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )
        await self.emit_event(execution_id, event)
```

Add the two settings to `settings.py` (near the other execution settings):

```python
    stream_buffer_ttl_seconds: int = 600
    stream_buffer_max_events: int = 2000
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_debug_event_manager_stream.py -v`
Expected: PASS.

- [ ] **Step 5: Guard against regressions in existing debug-event tests**

Run: `source .venv/bin/activate && pytest tests/ -k debug_event -v`
Expected: PASS (existing behavior preserved; `emit_event` still enqueues).

- [ ] **Step 6: Commit**

```bash
git add assemblix_api/execution/debug_event_manager.py assemblix_api/core/settings.py tests/unit/test_debug_event_manager_stream.py
git commit -m "feat(streaming): buffer-backed DebugEventManager with emit_stream_delta/subscribe"
```

---

### Task 8: Request-level `stream` flag → `ExecutionContext.stream_enabled` + buffer activation

**Files:**
- Modify: `assemblix_api/dto/requests/execution.py:14-49`
- Modify: `assemblix_api/schemas/execution.py:33-85` (add field)
- Modify: `assemblix_api/api/rest/executions.py` (dispatch: create the stream when `is_debug OR stream`; pass `stream` into context building)
- Test: `tests/integration/test_execution_stream_endpoint.py` (activation part) + a unit assertion on the context

**Interfaces:**
- Produces: `ExecuteWorkflowRequest.stream: bool = False`; `ExecutionContext.stream_enabled: bool = False`. When a run is dispatched with `is_debug OR stream`, `debug_event_manager.create_stream(execution_id)` is called so `is_streaming` is True and the buffer collects events.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_execution_stream_endpoint.py (part 1)
import pytest


@pytest.mark.asyncio
async def test_execute_with_stream_true_opens_a_subscribable_stream(client, seeded_text_workflow):
    # Arrange / Act — task=true so we get an execution_id back immediately
    resp = await client.post(
        f"/api/workflows/{seeded_text_workflow.id}/execute",
        json={"input": {"message": "hi"}, "task": True, "stream": True},
        headers=auth_headers(seeded_text_workflow),
    )
    # Assert
    assert resp.status_code == 202
    execution_id = resp.json()["executionId"]
    # The subscribe endpoint must find an active stream (not 404).
    stream_resp = await client.get(
        f"/api/executions/{execution_id}/stream",
        headers=auth_headers(seeded_text_workflow),
    )
    assert stream_resp.status_code == 200
    assert stream_resp.headers["content-type"].startswith("text/event-stream")
```

(Use the repo's existing execution-integration fixtures/harness from `rules/writing-tests.md`; `seeded_text_workflow` is a START→AGENT(text)→END workflow, `auth_headers` the standard token helper. The endpoint itself lands in Task 10 — this test is written now and goes green after Tasks 8+10; run it at the end of Task 10.)

- [ ] **Step 2: Add the DTO + context fields**

`dto/requests/execution.py` — add after `task`:

```python
    stream: bool = Field(
        default=False,
        description="If true, stream text deltas from streamable agent nodes over SSE (subscribe via GET /executions/{id}/stream)",
    )
```

`schemas/execution.py` — add to `ExecutionContext` (after `db_checkpoint` default is fine; it is a plain bool with a default):

```python
    # True when the run was dispatched with request.stream — the per-node delta sink is
    # only built when this is set (the request-level gate; node-level gate lives on the node).
    stream_enabled: bool = False
```

- [ ] **Step 3: Thread `stream` through dispatch + activate the buffer**

In `executions.py`, where the debug flag currently decides `create_stream` (the `_dispatch_debug_stream` / `_dispatch_sync` area, `is_debug` handling): call `create_stream` when `is_debug or request.stream`, and propagate `stream_enabled=request.stream` into the `ExecutionContext` built for the run (the context is assembled in the preparation phase / `build_executor` inputs — set `stream_enabled` from the request there). Concretely, find the single place the context is constructed for a run and pass `stream_enabled=request.stream`; find the single place `debug_event_manager.create_stream(...)` is called and change its guard from `is_debug` to `is_debug or request.stream`.

- [ ] **Step 4: Unit-assert the context carries the flag**

```python
# tests/unit/test_agent_node_stream_gate.py (part 1)
from assemblix_api.schemas.execution import ExecutionContext


def test_context_defaults_stream_disabled(make_context):
    ctx = make_context()  # existing unit fixture building a minimal ExecutionContext
    assert ctx.stream_enabled is False
```

Run: `source .venv/bin/activate && pytest tests/unit/test_agent_node_stream_gate.py::test_context_defaults_stream_disabled -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/dto/requests/execution.py assemblix_api/schemas/execution.py assemblix_api/api/rest/executions.py tests/unit/test_agent_node_stream_gate.py tests/integration/test_execution_stream_endpoint.py
git commit -m "feat(streaming): request-level stream flag activates the execution buffer"
```

---

### Task 9: Node-level `stream` flag + three-gate wiring in `AgentNode`/`NodeRunner`

Covers **A1–A4** (three-gate) and the `validate_config` warning.

**Files:**
- Modify: `assemblix_api/schemas/node.py:72-123` (add `stream`)
- Modify: `assemblix_api/schemas/execution.py:149-153` (add `NodeInput.on_delta`)
- Modify: `assemblix_api/execution/node_runner.py:55-61` (build the sink)
- Modify: `assemblix_api/execution/workflow_executor.py` (pass `node_id`/`step_number` to `NodeRunner.run` at both call sites)
- Modify: `assemblix_api/nodes/agent_node.py:56-144, 239-256` (apply the format gate; validation warning)
- Test: `tests/unit/test_agent_node_stream_gate.py`

**Interfaces:**
- Consumes: `AgentRunner.run(on_delta=...)` (Task 3), `DebugEventManager.emit_stream_delta` (Task 7), `ExecutionContext.stream_enabled` (Task 8).
- Produces: `AgentNodeConfig.stream: bool = False`; `NodeInput.on_delta: Callable[[str], Awaitable[None]] | None = None`. `AgentNode.execute` passes `on_delta` to `AgentRunner` iff `cfg.stream and not parse_json and node_input.on_delta is not None`.

- [ ] **Step 1: Write the failing tests (three-gate)**

```python
# tests/unit/test_agent_node_stream_gate.py (part 2)
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "req_stream,node_stream,response_format,expect_deltas",
    [
        (True, True, "text", True),          # A4 — all gates open
        (False, True, "text", False),        # A1 — request gate closed
        (True, False, "text", False),        # A2 — node gate closed
        (True, True, "json_object", False),  # A3 — format gate closed
    ],
)
async def test_three_gate_delta_emission(
    mock_llm, make_agent_node, run_node, req_stream, node_stream, response_format, expect_deltas
):
    # Arrange
    mock_llm.set_stream(["Hel", "lo"])
    mock_llm.set_response('{"k": "v"}' if response_format == "json_object" else "Hello")
    node = make_agent_node(stream=node_stream, response_format=response_format)
    deltas: list[str] = []

    # Act — run_node wires a NodeRunner with a real DebugEventManager, stream_enabled=req_stream,
    # and records emitted STREAM_DELTA payloads into `deltas`.
    await run_node(node, stream_enabled=req_stream, on_delta_sink=deltas.append)

    # Assert
    assert (len(deltas) > 0) is expect_deltas
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/test_agent_node_stream_gate.py -k three_gate -v`
Expected: FAIL — `AgentNodeConfig` has no `stream`, `NodeInput` has no `on_delta`.

- [ ] **Step 3: Add the config + input fields**

`schemas/node.py` — add to `AgentNodeConfig` (after `response_schema`):

```python
    # Stream this agent's free-form text output token-by-token to the client when the run
    # is dispatched with request.stream=true. Only honored for response_format="text".
    stream: bool = False
```

`schemas/execution.py` — add to `NodeInput`:

```python
@dataclass
class NodeInput:
    data: dict
    context: ExecutionContext
    # Per-run delta sink, set by NodeRunner when the run streams; agent nodes forward it to
    # AgentRunner. None for non-streaming runs and non-agent nodes.
    on_delta: Callable[[str], Awaitable[None]] | None = None
```

- [ ] **Step 4: Build the sink in `NodeRunner.run`**

`node_runner.py` — change `run` to accept the node identity and build the sink:

```python
    async def run(
        self, node, node_input: NodeInput, *, node_id: str, step_number: int
    ) -> NodeOutput:
        ctx = node_input.context
        if ctx.stream_enabled and self._debug_event_manager.is_streaming(ctx.execution_id):
            execution_id = ctx.execution_id

            async def _sink(text: str) -> None:
                await self._debug_event_manager.emit_stream_delta(
                    execution_id, step_number=step_number, node_id=node_id, delta=text
                )

            node_input.on_delta = _sink

        set_nodes_in_progress(+1)
        try:
            return await node.execute(node_input)
        finally:
            set_nodes_in_progress(-1)
```

`workflow_executor.py` — at the two `node_runner.run(node, node_input)` call sites (sequential ~`:639`, parallel ~`:819`), pass the identity the loop already has:

```python
await node_runner.run(node, node_input, node_id=current_node_id, step_number=step_number)
```

(In the parallel path use that branch's node id / step number variables.)

- [ ] **Step 5: Apply the format gate in `AgentNode.execute`**

In `agent_node.py`, at the `AgentRunner().run(...)` call (`:135-144`), pass `on_delta` subject to the format gate:

```python
            on_delta = node_input.on_delta if (cfg.stream and not parse_json) else None
            result = await AgentRunner().run(
                model=model,
                provider=cfg.provider.value,
                model_name=cfg.model,
                instructions=instructions or None,
                conversation=conversation,
                toolsets=toolsets,
                parse_json=parse_json,
                total_timeout=total_timeout,
                on_delta=on_delta,
            )
```

Add the validation warning in `validate_config` (append to `errors`, which the canvas renders as warnings):

```python
        if self.typed_config.stream and self.typed_config.response_format == "json_object":
            errors.append("Streaming is ignored for json_object output; set response_format=text to stream")
```

- [ ] **Step 6: Run the three-gate tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/test_agent_node_stream_gate.py -v`
Expected: PASS (A1–A4).

- [ ] **Step 7: Run the node/executor unit suites for regressions**

Run: `source .venv/bin/activate && pytest tests/unit/ -k "agent_node or node_runner or workflow_executor" -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add assemblix_api/schemas/node.py assemblix_api/schemas/execution.py assemblix_api/execution/node_runner.py assemblix_api/execution/workflow_executor.py assemblix_api/nodes/agent_node.py tests/unit/test_agent_node_stream_gate.py
git commit -m "feat(streaming): per-node stream flag with three-gate delta emission"
```

---

### Task 10: `GET /api/executions/{id}/stream` SSE endpoint

Covers **C13** (buffer expired → 404 fallback) and the transport for Task 8's activation test.

**Files:**
- Modify: `assemblix_api/api/rest/executions.py` (new endpoint on `execution_detail_router`)
- Test: `tests/integration/test_execution_stream_endpoint.py`

**Interfaces:**
- Consumes: `DebugEventManager.is_streaming` / `subscribe` (Task 7), scope auth helpers already in `executions.py`.
- Produces: `GET /api/executions/{execution_id}/stream` → `StreamingResponse(media_type="text/event-stream")`. Honors `Last-Event-ID` header (falls back to `?cursor=`); `404` when the execution has no active stream; SSE frames `id: <seq>\nevent: <type>\ndata: <json>\n\n`; a `: keepalive` comment every ~25s idle; returns after the terminal event.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_execution_stream_endpoint.py (part 2)
@pytest.mark.asyncio
async def test_stream_delivers_deltas_then_completes(client, seeded_streamable_workflow):
    # seeded_streamable_workflow: START -> AGENT(text, stream=True) -> END
    resp = await client.post(
        f"/api/workflows/{seeded_streamable_workflow.id}/execute",
        json={"input": {"message": "hi"}, "task": True, "stream": True},
        headers=auth_headers(seeded_streamable_workflow),
    )
    execution_id = resp.json()["executionId"]

    body = await read_sse(client, f"/api/executions/{execution_id}/stream",
                          headers=auth_headers(seeded_streamable_workflow))
    # Assert: at least one stream_delta, and a terminal execution_complete
    assert any(evt["event"] == "stream_delta" for evt in body)
    assert body[-1]["event"] == "execution_complete"


@pytest.mark.asyncio
async def test_stream_404_when_no_active_stream(client, seeded_streamable_workflow):
    from uuid import uuid4
    resp = await client.get(
        f"/api/executions/{uuid4()}/stream",
        headers=auth_headers(seeded_streamable_workflow),
    )
    assert resp.status_code == 404  # C13 — client falls back to GET /workflows/task/{id}
```

(`read_sse` is a small helper that consumes the streaming body and parses SSE frames into `{"event":..., "data":...}` dicts; add it to the test module or `tests/plugins`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/integration/test_execution_stream_endpoint.py -v`
Expected: FAIL — 404 route not found / `read_sse` missing.

- [ ] **Step 3: Implement the endpoint**

In `executions.py`, add (reuse the existing DI for the debug event manager and the scope guard used by `GET /executions/{execution_id}`):

```python
@execution_detail_router.get("/{execution_id}/stream")
async def stream_execution_events(
    execution_id: UUID,
    request: Request,
    scope=Depends(require_execution_scope),  # same scope dep the detail route uses
    debug_event_manager: DebugEventManager = Depends(get_debug_event_manager),
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """Subscribe to an execution's event stream (step events + text deltas) over SSE.

    Replays from the Last-Event-ID cursor, then tails live until the terminal event. 404
    when no live buffer exists (expired or a non-streaming run) — the client then falls
    back to GET /workflows/task/{execution_id} for the final result.
    """
    await _authorize_execution(execution_id, scope, execution_service)  # 404/403 as elsewhere

    if not debug_event_manager.is_streaming(execution_id):
        raise HTTPException(status_code=404, detail="No active stream for this execution")

    last_event_id = request.headers.get("last-event-id")
    cursor = int(last_event_id) if last_event_id else int(request.query_params.get("cursor", 0))

    async def event_generator():
        subscription = debug_event_manager.subscribe(execution_id, after_seq=cursor)
        while True:
            try:
                event = await asyncio.wait_for(subscription.__anext__(), timeout=25.0)
            except StopAsyncIteration:
                break
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield (
                f"id: {event.seq}\n"
                f"event: {event.event_type.value}\n"
                f"data: {event.model_dump_json()}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

(Import `Request`, `HTTPException`, `asyncio` if not already imported; `_authorize_execution` / `require_execution_scope` mirror the existing `GET /executions/{execution_id}` guards — reuse them verbatim.)

- [ ] **Step 4: Run the endpoint tests + the Task 8 activation test**

Run: `source .venv/bin/activate && pytest tests/integration/test_execution_stream_endpoint.py -v`
Expected: PASS (delivery, 404, and the activation test from Task 8).

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/api/rest/executions.py tests/integration/test_execution_stream_endpoint.py
git commit -m "feat(streaming): GET /executions/{id}/stream SSE endpoint with cursor replay"
```

---

### Task 11: TTL cleanup for the buffer

**Files:**
- Modify: `assemblix_api/execution/debug_event_manager.py` (drop the buffer after completion + TTL)
- Modify: `assemblix_api/execution/workflow_executor.py` (schedule cleanup at finalization, next to the existing `cleanup_stream`)
- Test: `tests/unit/test_debug_event_manager_stream.py`

**Interfaces:**
- Produces: `DebugEventManager.schedule_stream_cleanup(execution_id)` — after `settings.stream_buffer_ttl_seconds`, calls `self._buffer.drop(execution_id)` and the existing `cleanup_stream`. Called once the terminal event is emitted.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/unit/test_debug_event_manager_stream.py
@pytest.mark.asyncio
async def test_buffer_dropped_after_ttl(monkeypatch):
    mgr = DebugEventManager()
    eid = uuid4()
    mgr.create_stream(eid)
    # ttl=0 → immediate drop after the scheduled task runs
    monkeypatch.setattr("assemblix_api.core.settings.get_settings",
                        lambda: _settings_with(stream_buffer_ttl_seconds=0))
    mgr.schedule_stream_cleanup(eid)
    await asyncio.sleep(0.01)
    assert mgr.is_streaming(eid) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_debug_event_manager_stream.py -k ttl -v`
Expected: FAIL — `schedule_stream_cleanup` not defined.

- [ ] **Step 3: Implement cleanup**

```python
    def schedule_stream_cleanup(self, execution_id: UUID) -> None:
        ttl = get_settings().stream_buffer_ttl_seconds

        async def _drop_later() -> None:
            await asyncio.sleep(ttl)
            self._buffer.drop(execution_id)
            self.cleanup_stream(execution_id)

        asyncio.create_task(_drop_later())
```

(Import `get_settings`.) In `workflow_executor.py` finalization/error, right after `emit_execution_complete` / `emit_error`, call `self._debug_event_manager.schedule_stream_cleanup(execution_id)` instead of an immediate `cleanup_stream` (so a subscriber connecting just after completion can still replay within the TTL).

- [ ] **Step 4: Run to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_debug_event_manager_stream.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/execution/debug_event_manager.py assemblix_api/execution/workflow_executor.py tests/unit/test_debug_event_manager_stream.py
git commit -m "feat(streaming): TTL cleanup of the per-execution stream buffer"
```

---

### Task 12: Integration — error mid-stream, parallel demux, non-stream regression

Covers **D14** (mid-stream error → FAILED), **D15** (parallel demux by node_id), **E16** (non-stream debug byte-for-byte).

**Files:**
- Test: `tests/integration/test_streaming_e2e.py`

**Interfaces:**
- Consumes: everything above. No new production code unless a test surfaces a gap.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_streaming_e2e.py
import pytest


@pytest.mark.asyncio
async def test_error_mid_stream_marks_failed_and_keeps_partial_deltas(
    client, mock_llm, seeded_streamable_workflow
):  # D14
    mock_llm.set_stream(["par", "tial"])
    mock_llm.set_error_after_stream(RuntimeError("provider exploded"))  # mock hook: raise on drain
    resp = await client.post(
        f"/api/workflows/{seeded_streamable_workflow.id}/execute",
        json={"input": {"message": "hi"}, "task": True, "stream": True},
        headers=auth_headers(seeded_streamable_workflow),
    )
    execution_id = resp.json()["executionId"]
    body = await read_sse(client, f"/api/executions/{execution_id}/stream",
                          headers=auth_headers(seeded_streamable_workflow))
    assert any(e["event"] == "stream_delta" for e in body)   # partials delivered
    assert body[-1]["event"] == "error"
    # And the execution row is FAILED
    detail = await client.get(f"/api/executions/{execution_id}",
                              headers=auth_headers(seeded_streamable_workflow))
    assert detail.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_parallel_streamable_agents_demux_by_node_id(
    client, mock_llm, seeded_parallel_streamable_workflow
):  # D15
    body = await run_and_collect(client, seeded_parallel_streamable_workflow, stream=True)
    node_ids = {e["data"]["nodeId"] for e in body if e["event"] == "stream_delta"}
    assert len(node_ids) == 2  # deltas from both agents, distinguishable


@pytest.mark.asyncio
async def test_non_stream_debug_event_set_unchanged(
    client, mock_llm, seeded_streamable_workflow
):  # E16
    body = await run_and_collect(client, seeded_streamable_workflow, stream=False, is_debug=True)
    assert not any(e["event"] == "stream_delta" for e in body)
    assert [e["event"] for e in body][:1] == ["step_start"]  # same opening event as before
```

(Add the `mock_llm.set_error_after_stream(exc)` hook in `tests/plugins/llm.py`: after yielding the armed chunks, `raise exc` from the async iterator. `run_and_collect` posts the execute then reads the SSE.)

- [ ] **Step 2: Run to verify they fail**

Run: `source .venv/bin/activate && pytest tests/integration/test_streaming_e2e.py -v`
Expected: FAIL initially (missing fixtures/hook).

- [ ] **Step 3: Add the mock hook + fixtures, then implement any gaps**

Add `set_error_after_stream` to `LLMMock` and the `_AsyncChunkStream` raise-after-drain behavior. Add `seeded_parallel_streamable_workflow` (two parallel AGENT(text, stream=True) nodes joining to END). If a test fails for a real reason (e.g. error mid-stream does not emit the partials before `error`), fix the production code — the streaming path in Task 3/9 must `await on_delta` as chunks arrive, before the exception propagates, which it does since deltas fire inside the run.

- [ ] **Step 4: Run to verify they pass**

Run: `source .venv/bin/activate && pytest tests/integration/test_streaming_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Full backend suite + gates**

Run: `source .venv/bin/activate && make check`
Expected: PASS (ruff, mypy, pytest).

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_streaming_e2e.py tests/plugins/llm.py
git commit -m "test(streaming): mid-stream error, parallel demux, non-stream regression"
```

---

### Task 13: Frontend — debug-runner streaming toggle + delta rendering

**Files:**
- Locate + modify: the debug-runner send control and its SSE consumer under `assemblix-app-web/src/`.

**Interfaces:**
- Consumes: `GET /api/executions/{id}/stream` (Task 10), `stream` request field (Task 8), node `stream` flag (Task 9).

- [ ] **Step 1: Locate the debug SSE consumer**

Run: `cd assemblix-app-web && grep -rn "execute/debug\|EventSource\|text/event-stream\|task/" src/`
Identify the component that today sends the debug run and consumes step events. Note its path for the steps below.

- [ ] **Step 2: Add a "streaming" toggle to the debug send control**

In the located send component, add a checkbox (i18n key `debug.streaming`) whose state is `streamEnabled`. When sending: if `streamEnabled`, include `stream: true, task: true` in the execute body and, on the `202`, open `new EventSource('/api/executions/' + executionId + '/stream')`. When off, send exactly today's body (no `stream` field) — preserving current behavior byte-for-byte.

- [ ] **Step 3: Render deltas per node**

Handle the new event on the EventSource, appending deltas to a per-node buffer keyed by `data.nodeId`:

```ts
es.addEventListener('stream_delta', (e) => {
  const { nodeId, delta } = JSON.parse((e as MessageEvent).data).data;
  appendDelta(nodeId, delta);           // accumulate into the node's live text
});
es.addEventListener('step_complete', (e) => { /* reconcile node output as today */ });
es.addEventListener('execution_complete', () => es.close());
es.addEventListener('error', () => es.close());
```

Track `lastEventId` from each event's `id` for reconnect (`EventSource` sends `Last-Event-ID` automatically on reconnect; the endpoint replays from it).

- [ ] **Step 4: Type-check (the hard CI gate)**

Run: `cd assemblix-app-web && yarn build`
Expected: type-check passes.

- [ ] **Step 5: Commit**

```bash
git add assemblix-app-web/src
git commit -m "feat(streaming): debug-runner streaming toggle and live delta rendering"
```

---

### Task 14: End-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Backend SSE smoke via curl**

Start the stack (`docker compose -f docker-compose.dev.yml up postgres` + `make dev`), create a workflow START→AGENT(text, stream=true)→END, then:

```bash
EID=$(curl -s -X POST localhost:8000/api/workflows/$WF/execute \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"input":{"message":"tell me a short story"},"task":true,"stream":true}' | jq -r .executionId)
curl -N localhost:8000/api/executions/$EID/stream -H "Authorization: Bearer $TOKEN"
```

Expected: `id:`/`event: stream_delta`/`data:` frames arriving incrementally, ending with `event: execution_complete`.

- [ ] **Step 2: Reconnect check**

Kill the curl mid-stream, reconnect with `-H "Last-Event-ID: <last seq seen>"`; expect only events after that seq (no dupes, no loss).

- [ ] **Step 3: Browser dogfood**

In the debug runner, toggle streaming on, send a message, watch tokens render live; toggle off, send again, confirm behavior identical to before streaming existed. Use the `browse`/gstack skill or manual QA.

- [ ] **Step 4: Update the memory + initiative note**

Record that Phase 2a (text streaming) is implemented on this branch; 2b (audio chunks) is next. (No commit needed — memory files.)

---

## Self-Review

**1. Spec coverage:**
- §2 In-scope: node `stream` (T9) ✓, request `stream` (T8) ✓, `STREAM_DELTA` (T4) ✓, buffer two backends (T5/T6) ✓, `GET /executions/{id}/stream` (T10) ✓, AgentRunner streaming + shim (T1/T3) ✓, frontend toggle (T13) ✓, mock seam (T2) ✓.
- §3.1 three-gate (T9/A1–A4) ✓; §3.3 replayable log + seq (T4/T5) ✓; §3.4 buffer closes the race (T5 subscribe semantics) ✓; §3.5 AgentRunner (T3) ✓; §3.6 shim (T1) ✓; §3.8 non-stream identical (T12/E16) ✓; §3.9 no delta persistence (no DB writes added; asserted by "no migration") ✓; §3.10 bus active on `is_debug OR stream` (T8) ✓; §6 error handling (T12/D14) ✓; §7 settings (T7) ✓; §8 tests (all confirmed cases mapped) ✓.
- Test-case map: A1–A4→T9; B5–B7→T3; C8–C10,C12→T5; C11→T6; C13→T10; D14–D15→T12; E16→T12; E17→T2. All covered.

**2. Placeholder scan:** No "TBD"/"handle edge cases" left. Two deliberate locate-then-edit points (T8 dispatch site, T13 frontend component) give the exact grep and the exact code to add — acceptable because the surrounding code isn't in this plan's read set; every code block is concrete.

**3. Type consistency:** `emit_stream_delta(execution_id, *, step_number, node_id, delta)` (T7) matches the `_sink` call (T9) and `StreamDeltaEventData(node_id, step_number, delta)` (T4). `subscribe(execution_id, after_seq)` consistent across T5/T6/T7/T10. `AgentRunner.run(..., on_delta=...)` (T3) matches the AgentNode call (T9). `DebugEvent.seq` (T4) is written by `append` (T5/T6) and read by the endpoint (T10). `is_streaming`/`is_open` split (manager delegates to buffer) consistent. `NodeInput.on_delta` (T9) set by NodeRunner (T9), read by AgentNode (T9).

**Note on the Redis path (T6):** required only for cross-process/queued streaming. Debug runs execute inline, so the demoable path uses the in-memory buffer end-to-end; T6 can be deferred if the team wants to ship the debug consumer first, at the cost of not streaming queued production runs. Flagged, not silently dropped.
