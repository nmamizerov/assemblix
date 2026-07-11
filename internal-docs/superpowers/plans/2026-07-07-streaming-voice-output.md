# Streaming Voice Output (Phase 2b — realtime agent→TTS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream an agent's spoken output in real time — the speaking AGENT node feeds its text tokens into an ElevenLabs WebSocket as it generates, and PCM audio chunks flow back to the client as `AUDIO_DELTA` events on the existing 2a stream.

**Architecture:** Voice modality moves from END to the AGENT node (`output_type: text|voice` + `voice`). When a run streams and the agent is voice+realtime-capable, the node opens a `RealtimeTTSSession` (EL `stream-input` WS), tees each text delta into it, and a concurrent receive loop emits `AUDIO_DELTA` (base64 PCM + alignment). Audio rides the same buffer/SSE as 2a text but under a **transient (live-only)** retention class so heavy PCM never starves replayable text/control. END loses all synthesis (no double-call possible). The non-streaming path synthesizes one buffered base64 blob at the agent (migrated phase-1 logic). The only UI consumer is the debug runner, with a greenfield Web Audio PCM player.

**Tech Stack:** Python 3.13, FastAPI, pydantic-ai, `websockets` (new dep), asyncio; React 19 + TypeScript, RTK Query, Web Audio API (new); ElevenLabs `stream-input` WS.

## Global Constraints

- **TDD, two stages:** write the failing test first, then the minimal implementation. Backend only. (`assemblix-app-api/CLAUDE.md`.)
- **§0 — new-feature test cases come from the user.** Before writing any test in a task, the concrete cases (inputs/expected/edges/errors) must be confirmed by the user. This plan lists the intended cases per task; treat them as the *proposal* to confirm, not a licence to invent. (`assemblix-app-api/rules/writing-tests.md` §0.)
- **AAA mandatory** in every test: explicit `# Arrange` / `# Act` / `# Assert`, one meaningful call in Act. (`rules/writing-tests.md` §2.)
- **Never alter existing test assertions** to make them pass; a failing existing test means the implementation is wrong — stop and ask. Mechanical edits (imports/rename/format) are fine. (`rules/writing-tests.md` §0.)
- **Activate the venv** (`source .venv/bin/activate`) before any Python command. Install deps only via `uv add`. (`CLAUDE.md`.)
- **Backend layers:** DTOs between layers, no business logic in routers/repositories, no `HTTPException` in repositories, no SQLAlchemy in services. (`CLAUDE.md`.)
- **Redis stays optional for self-host:** the default path (no Redis, inline) must work fully; Redis is only for the queued/worker tier. No new Redis requirement.
- **Non-streaming and text-only behavior must stay byte-for-byte identical.** Audio is best-effort and never fails a run.
- **DTOs are camelCase on the wire** via `DTOModel` aliasing; frontend types stay camelCase.
- **Conventional Commits** for every commit (`feat:`, `test:`, `refactor:`, `docs:`, `style:`). Do not push or open PRs.
- **Frontend has no unit tests** — gate is `yarn build` (type-check) + browser dogfood.
- Work on branch `feat/streaming-voice-output` (already created; the spec commit `e77d1f1` is its first commit).

**Spec:** `docs/superpowers/specs/2026-07-07-streaming-voice-output-design.md`.

---

## File Structure

**Backend — create:**
- `assemblix_api/external/voice/realtime.py` — `RealtimeTTSSession` (EL `stream-input` WS client) + `AlignmentPayload` parsing.
- `assemblix_api/nodes/agent_voice.py` — the voice orchestration helper for the agent node (gate, live session tee, buffered fallback, cost facts). Keeps `agent_node.execute` lean.
- `tests/plugins/tts_ws.py` — `mock_tts_ws` fixture: a fake EL WS arming scripted audio chunks + alignment (mirrors `mock_llm`).

**Backend — modify:**
- `assemblix_api/external/voice/base.py` — add `"realtime"` to the `route` Literal.
- `assemblix_api/external/voice/models/elevenlabs.json` — add realtime-capable model entries.
- `assemblix_api/external/voice/voice_catalog.py` — `has_realtime_route(provider, model)` helper.
- `assemblix_api/schemas/debug_events.py` — `AUDIO_DELTA`, `AudioDeltaEventData`, `AlignmentData`.
- `assemblix_api/schemas/execution.py` — `NodeInput.on_audio`.
- `assemblix_api/schemas/node.py` — `AgentNodeConfig.output_type` + `voice`; remove voice fields from `EndNodeConfig`.
- `assemblix_api/execution/stream_buffer.py` — transient audio class (`append_transient` + merged `subscribe`) for both backends.
- `assemblix_api/execution/debug_event_manager.py` — `emit_audio_delta`.
- `assemblix_api/execution/node_runner.py` — build the `on_audio` sink alongside `on_delta`.
- `assemblix_api/nodes/agent_node.py` — call the voice helper.
- `assemblix_api/nodes/end_node.py` — remove `_synthesize_into`, the voice branch, and voice imports.
- `assemblix_api/core/settings.py` — new settings.

**Frontend — create:**
- `src/entities/workflow/lib/workflow-editor/lib/use-pcm-player.ts` — Web Audio streaming PCM player.

**Frontend — modify:**
- `src/entities/workflow/model/types.ts` — `AgentNodeConfig` add `outputType`/`voice`; remove voice from `EndNodeConfig`.
- `src/entities/workflow/lib/workflow-editor/ui/node-forms/agent-node-form.tsx` — output-type select + voice picker (moved in).
- `src/entities/workflow/lib/workflow-editor/ui/node-forms/end-node-form.tsx` — remove the voice picker.
- `src/entities/workflow/lib/workflow-editor/lib/use-workflow-debug.ts` + `ui/debug/execution-viewer.tsx` — handle `audio_delta` events → PCM player.

---

## Task 0: Spike — ElevenLabs `stream-input` WS + Web Audio PCM (de-risk, no test)

**Files:**
- Modify (append findings): `docs/superpowers/specs/2026-07-07-streaming-voice-output-design.md` (§11 spike results).
- Scratch: a throwaway `scripts/spike_tts_ws.py` (delete before the next task's commit).

This task produces **findings**, not shippable code. It is not TDD.

- [ ] **Step 1: Confirm the WS library and connection**

Run `source .venv/bin/activate && uv add websockets` (unless the spike finds the ElevenLabs SDK's WS is preferable — decide here). Write a scratch script that connects to `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id=eleven_flash_v2_5&output_format=pcm_16000` with header/`xi_api_key`, sends BOS `{"text": " ", "voice_settings": {...}, "generation_config": {"chunk_length_schedule": [50, 120, 200]}}`, a couple of text chunks `{"text": "Hello world. ", "try_trigger_generation": true}`, then EOS `{"text": ""}`.

- [ ] **Step 2: Record the exact receive-message shape**

Capture and write down: the audio field name (`audio`, base64), the alignment field name/shape (`normalizedAlignment` → `{chars, charStartTimesMs, charDurationsMs}` or `{char_start_times_ms, ...}`), the `isFinal` flag, and the socket-close semantics after EOS. Note whether PCM at `pcm_16000` is signed 16-bit LE mono.

- [ ] **Step 3: Confirm billed-character accounting**

Note whether ElevenLabs bills per input character sent (drives §Metering: count chars fed to `send_text`).

- [ ] **Step 4: Prototype gapless Web Audio playback**

In a scratch HTML file, decode base64 → `Int16Array` → `Float32Array` (`/32768`) → `AudioBuffer` (1 ch, 16000 Hz), schedule `AudioBufferSourceNode`s back-to-back tracking a `nextStartTime` cursor. Confirm gapless playback. This locks the `use-pcm-player.ts` approach.

- [ ] **Step 5: Write findings into the spec and delete the scratch script**

Append a "Spike results (2026-07-07)" block to spec §11 with the confirmed message shapes, PCM format, alignment key names, and the chosen WS lib. Delete `scripts/spike_tts_ws.py`.

```bash
rm -f scripts/spike_tts_ws.py
git add docs/superpowers/specs/2026-07-07-streaming-voice-output-design.md pyproject.toml uv.lock
git commit -m "docs(voice-streaming): spike results — EL stream-input WS + Web Audio PCM"
```

> The concrete field names below (`char_start_times_ms`, etc.) are the plan's assumption; if the spike finds ElevenLabs uses camelCase (`charStartTimesMs`), keep the internal `AlignmentData` snake_case and map at the parse boundary in `realtime.py`.

---

## Task 1: `AUDIO_DELTA` event schema

**Files:**
- Modify: `assemblix_api/schemas/debug_events.py`
- Test: `tests/unit/test_audio_delta_event.py`

**Interfaces:**
- Produces: `DebugEventType.AUDIO_DELTA = "audio_delta"`; `AlignmentData(chars: list[str], char_start_times_ms: list[int], char_durations_ms: list[int])`; `AudioDeltaEventData(node_id: str, step_number: int, audio: str, format: str = "pcm_16000", alignment: AlignmentData | None = None)`.

**Intended test cases (confirm with user per §0):** (a) `AudioDeltaEventData` serializes with camelCase aliases (`stepNumber`, `charStartTimesMs`); (b) `alignment=None` is allowed and serializes to `null`; (c) the new enum member equals `"audio_delta"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_audio_delta_event.py
from assemblix_api.schemas.debug_events import (
    AlignmentData,
    AudioDeltaEventData,
    DebugEventType,
)


def test_audio_delta_event_data_serializes_camelcase():
    # Arrange
    data = AudioDeltaEventData(
        node_id="agent-1",
        step_number=3,
        audio="QUJD",
        alignment=AlignmentData(
            chars=["H", "i"], char_start_times_ms=[0, 40], char_durations_ms=[40, 60]
        ),
    )
    # Act
    dumped = data.model_dump(by_alias=True)
    # Assert
    assert dumped["nodeId"] == "agent-1"
    assert dumped["stepNumber"] == 3
    assert dumped["format"] == "pcm_16000"
    assert dumped["alignment"]["charStartTimesMs"] == [0, 40]


def test_audio_delta_allows_no_alignment():
    # Arrange / Act
    data = AudioDeltaEventData(node_id="a", step_number=1, audio="QQ==")
    # Assert
    assert data.alignment is None
    assert DebugEventType.AUDIO_DELTA.value == "audio_delta"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_audio_delta_event.py -v`
Expected: FAIL — `ImportError: cannot import name 'AudioDeltaEventData'`.

- [ ] **Step 3: Implement the schema**

In `assemblix_api/schemas/debug_events.py`, add `AUDIO_DELTA = "audio_delta"` to `DebugEventType`, and after `StreamDeltaEventData`:

```python
class AlignmentData(DTOModel):
    """Character-level timing from the TTS provider (ElevenLabs normalizedAlignment).

    Carried through for phase-3 avatars/lip-sync; the phase-2b debug player ignores it.
    """

    chars: list[str]
    char_start_times_ms: list[int]
    char_durations_ms: list[int]


class AudioDeltaEventData(DTOModel):
    node_id: str
    step_number: int
    audio: str  # base64-encoded PCM chunk
    format: str = "pcm_16000"
    alignment: AlignmentData | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_audio_delta_event.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/schemas/debug_events.py tests/unit/test_audio_delta_event.py
git commit -m "feat(voice-streaming): AUDIO_DELTA event type + AlignmentData schema"
```

---

## Task 2: Settings for streaming voice

**Files:**
- Modify: `assemblix_api/core/settings.py`
- Test: `tests/unit/test_streaming_voice_settings.py`

**Interfaces:**
- Produces: `settings.stream_audio_buffer_max_chunks: int` (default 50); `settings.elevenlabs_ws_base_url: str`; `settings.voice_realtime_output_format: str` (default `"pcm_16000"`); `settings.voice_realtime_chunk_schedule: list[int]` (default `[50, 120, 200, 300]`).

**Intended test cases (confirm per §0):** defaults are present with the documented values; env overrides parse (`STREAM_AUDIO_BUFFER_MAX_CHUNKS`, `ELEVENLABS_WS_BASE_URL`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_streaming_voice_settings.py
from assemblix_api.core.settings import Settings


def test_streaming_voice_settings_have_defaults():
    # Arrange / Act
    s = Settings()
    # Assert
    assert s.stream_audio_buffer_max_chunks == 50
    assert s.voice_realtime_output_format == "pcm_16000"
    assert s.elevenlabs_ws_base_url.startswith("wss://")
    assert s.voice_realtime_chunk_schedule == [50, 120, 200, 300]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_streaming_voice_settings.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'stream_audio_buffer_max_chunks'`.

- [ ] **Step 3: Implement the settings**

In `assemblix_api/core/settings.py`, near the existing `stream_buffer_*` and `elevenlabs_api_base_url` lines, add:

```python
    stream_audio_buffer_max_chunks: int = int(os.getenv("STREAM_AUDIO_BUFFER_MAX_CHUNKS", "50"))
    elevenlabs_ws_base_url: str = os.getenv(
        "ELEVENLABS_WS_BASE_URL", "wss://api.elevenlabs.io/v1"
    )
    voice_realtime_output_format: str = os.getenv("VOICE_REALTIME_OUTPUT_FORMAT", "pcm_16000")
    voice_realtime_chunk_schedule: list[int] = field(
        default_factory=lambda: [
            int(x) for x in os.getenv("VOICE_REALTIME_CHUNK_SCHEDULE", "50,120,200,300").split(",")
        ]
    )
```

If `Settings` is a pydantic-settings model rather than a dataclass, use `Field(default_factory=...)` matching the file's existing style for list-valued settings; otherwise mirror the surrounding `int(os.getenv(...))` pattern. (Check the top of `settings.py` for whether `field` is already imported.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_streaming_voice_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/core/settings.py tests/unit/test_streaming_voice_settings.py
git commit -m "feat(voice-streaming): settings for realtime TTS + audio buffer"
```

---

## Task 3: In-memory transient audio buffer

**Files:**
- Modify: `assemblix_api/execution/stream_buffer.py`
- Test: `tests/unit/test_stream_buffer_audio.py`

**Interfaces:**
- Consumes: `DebugEvent`, `DebugEventType.AUDIO_DELTA` (Task 1).
- Produces: `InMemoryStreamBuffer.append_transient(execution_id, event) -> int` (assigns a monotonic seq shared with `append`, stores in a bounded audio ring, notifies subscribers); `subscribe` now merges retained + transient events in seq order.

**Intended test cases (confirm per §0):** (a) an audio event appended via `append_transient` is delivered live to a subscriber; (b) audio events are NOT retained for cursor replay beyond the ring — a subscriber that connects with `after_seq=0` after the ring overflowed misses the evicted audio but still receives all retained text/control; (c) seq stays monotonic across mixed `append`/`append_transient`; (d) a subscriber receives text and audio interleaved in seq order and stops at the terminal event.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_stream_buffer_audio.py
from datetime import datetime
from uuid import uuid4

import pytest

from assemblix_api.execution.stream_buffer import InMemoryStreamBuffer
from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType


def _evt(exec_id, etype):
    return DebugEvent(event_type=etype, execution_id=exec_id, timestamp=datetime.now(), data={})


@pytest.mark.asyncio
async def test_transient_audio_delivered_live_and_ordered():
    # Arrange
    buf = InMemoryStreamBuffer(max_events=2000, audio_max_chunks=50)
    exec_id = uuid4()
    buf.open(exec_id)
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STEP_START))
    await buf.append_transient(exec_id, _evt(exec_id, DebugEventType.AUDIO_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STREAM_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.EXECUTION_COMPLETE))
    # Act
    got = [e.event_type async for e in buf.subscribe(exec_id, after_seq=0)]
    # Assert
    assert got == [
        DebugEventType.STEP_START,
        DebugEventType.AUDIO_DELTA,
        DebugEventType.STREAM_DELTA,
        DebugEventType.EXECUTION_COMPLETE,
    ]


@pytest.mark.asyncio
async def test_audio_ring_overflow_does_not_evict_retained():
    # Arrange
    buf = InMemoryStreamBuffer(max_events=2000, audio_max_chunks=2)
    exec_id = uuid4()
    buf.open(exec_id)
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STEP_START))
    for _ in range(5):  # overflow the audio ring of 2
        await buf.append_transient(exec_id, _evt(exec_id, DebugEventType.AUDIO_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.EXECUTION_COMPLETE))
    # Act
    got = [e.event_type async for e in buf.subscribe(exec_id, after_seq=0)]
    # Assert — the retained control events survive; at most 2 audio remain
    assert got[0] == DebugEventType.STEP_START
    assert got[-1] == DebugEventType.EXECUTION_COMPLETE
    assert got.count(DebugEventType.AUDIO_DELTA) <= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stream_buffer_audio.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'audio_max_chunks'`.

- [ ] **Step 3: Implement transient audio in `InMemoryStreamBuffer`**

Edit `assemblix_api/execution/stream_buffer.py`:

```python
class InMemoryStreamBuffer:
    def __init__(self, max_events: int = 2000, audio_max_chunks: int = 50):
        self._max_events = max_events
        self._audio_max_chunks = audio_max_chunks
        self._events: dict[UUID, deque[DebugEvent]] = {}
        self._audio: dict[UUID, deque[DebugEvent]] = {}
        self._seq: dict[UUID, int] = {}
        self._conds: dict[UUID, asyncio.Condition] = {}

    def open(self, execution_id: UUID) -> None:
        self._events.setdefault(execution_id, deque(maxlen=self._max_events))
        self._audio.setdefault(execution_id, deque(maxlen=self._audio_max_chunks))
        self._seq.setdefault(execution_id, 0)
        self._conds.setdefault(execution_id, asyncio.Condition())

    async def append_transient(self, execution_id: UUID, event: DebugEvent) -> int:
        """Append a live-only event (audio). Shares the seq counter with append() but is
        stored in a small ring that is NOT part of cursor replay, so heavy PCM never
        evicts retained control/text events."""
        if execution_id not in self._events:
            self.open(execution_id)
        self._seq[execution_id] += 1
        event.seq = self._seq[execution_id]
        self._audio[execution_id].append(event)
        cond = self._conds[execution_id]
        async with cond:
            cond.notify_all()
        return event.seq
```

Rewrite `subscribe` to merge both deques:

```python
    async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        if execution_id not in self._events:
            return
        cond = self._conds[execution_id]
        cursor = after_seq

        def _pending() -> list[DebugEvent]:
            merged = [
                e
                for e in (*self._events[execution_id], *self._audio[execution_id])
                if e.seq > cursor
            ]
            merged.sort(key=lambda e: e.seq)
            return merged

        while True:
            for event in _pending():
                cursor = event.seq
                yield event
                if event.event_type in TERMINAL_EVENTS:
                    return
            async with cond:
                if _pending():
                    continue
                await cond.wait()
```

Also add `self._audio.pop(execution_id, None)` in `drop`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_stream_buffer_audio.py tests/unit/test_stream_buffer.py -v`
Expected: PASS (new tests pass; the existing `test_stream_buffer.py` still passes — subscribe behavior for retained-only events is unchanged).

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/execution/stream_buffer.py tests/unit/test_stream_buffer_audio.py
git commit -m "feat(voice-streaming): in-memory transient audio ring (live-only, no replay starvation)"
```

---

## Task 4: Redis transient audio (cross-process parity)

**Files:**
- Modify: `assemblix_api/execution/stream_buffer.py` (`RedisStreamBuffer`)
- Test: `tests/unit/test_stream_buffer_audio_redis.py`

**Interfaces:**
- Produces: `RedisStreamBuffer.append_transient(execution_id, event) -> int` (XADD to a small-`MAXLEN` `stream:audio:{id}`, shared seq via the existing `stream:seq:{id}` counter); `RedisStreamBuffer.subscribe` merges the events-stream and audio-stream by seq.

**Intended test cases (confirm per §0):** with `fakeredis`, a transient audio event is delivered live and interleaved by seq with retained text/control; the audio-stream is capped (`MAXLEN`) independently of the events-stream. Parity with the in-memory backend for the ordering test.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_stream_buffer_audio_redis.py
from datetime import datetime
from uuid import uuid4

import pytest

from assemblix_api.execution.stream_buffer import RedisStreamBuffer
from assemblix_api.schemas.debug_events import DebugEvent, DebugEventType


def _evt(exec_id, etype):
    return DebugEvent(event_type=etype, execution_id=exec_id, timestamp=datetime.now(), data={})


@pytest.mark.asyncio
async def test_redis_transient_audio_interleaves_by_seq(fake_redis):
    # Arrange
    buf = RedisStreamBuffer(fake_redis, max_events=2000, audio_max_chunks=50)
    exec_id = uuid4()
    buf.open(exec_id)
    await buf.append(exec_id, _evt(exec_id, DebugEventType.STEP_START))
    await buf.append_transient(exec_id, _evt(exec_id, DebugEventType.AUDIO_DELTA))
    await buf.append(exec_id, _evt(exec_id, DebugEventType.EXECUTION_COMPLETE))
    # Act
    got = [e.event_type async for e in buf.subscribe(exec_id, after_seq=0)]
    # Assert
    assert got == [
        DebugEventType.STEP_START,
        DebugEventType.AUDIO_DELTA,
        DebugEventType.EXECUTION_COMPLETE,
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stream_buffer_audio_redis.py -v`
Expected: FAIL — `TypeError`/`AttributeError` (no `audio_max_chunks` / no `append_transient`).

- [ ] **Step 3: Implement transient audio in `RedisStreamBuffer`**

```python
class RedisStreamBuffer:
    def __init__(self, redis: Any, max_events: int = 2000, audio_max_chunks: int = 50):
        self._redis = redis
        self._max_events = max_events
        self._audio_max_chunks = audio_max_chunks
        self._opened: set[UUID] = set()

    def _audio_key(self, execution_id: UUID) -> str:
        return f"stream:audio:{execution_id}"

    async def append_transient(self, execution_id: UUID, event: DebugEvent) -> int:
        seq = int(await self._redis.incr(f"stream:seq:{execution_id}"))
        event.seq = seq
        await self._redis.xadd(
            self._audio_key(execution_id),
            {"payload": event.model_dump_json()},
            maxlen=self._audio_max_chunks,
            approximate=True,
        )
        return seq
```

Rewrite `subscribe` to read both streams and merge by seq. Replay both retained ranges first (sorted by embedded `seq`), then live-tail both with a single `XREAD` over both keys:

```python
    async def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        events_key = self._key(execution_id)
        audio_key = self._audio_key(execution_id)
        last = {events_key: "0-0", audio_key: "0-0"}

        # Replay retained ranges from both streams, filtered by cursor, merged by seq.
        replay: list[DebugEvent] = []
        for key in (events_key, audio_key):
            for entry_id, fields in await self._redis.xrange(key):
                last[key] = entry_id
                ev = DebugEvent.model_validate_json(fields["payload"])
                if ev.seq > after_seq:
                    replay.append(ev)
        for ev in sorted(replay, key=lambda e: e.seq):
            yield ev
            if ev.event_type in TERMINAL_EVENTS:
                return

        # Live tail both streams.
        while True:
            resp = await self._redis.xread(last, block=25_000, count=100)
            if not resp:
                continue
            batch: list[DebugEvent] = []
            for stream_key, entries in resp:
                for entry_id, fields in entries:
                    last[stream_key] = entry_id
                    ev = DebugEvent.model_validate_json(fields["payload"])
                    if ev.seq > after_seq:
                        batch.append(ev)
            for ev in sorted(batch, key=lambda e: e.seq):
                yield ev
                if ev.event_type in TERMINAL_EVENTS:
                    return
```

> Note: `xread` keys must be `str`; `_key`/`_audio_key` already return strings. `fakeredis` returns entry field keys as `str` under the project's decode settings (matching the existing `RedisStreamBuffer` code that indexes `fields["payload"]`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_stream_buffer_audio_redis.py tests/unit/test_stream_buffer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/execution/stream_buffer.py tests/unit/test_stream_buffer_audio_redis.py
git commit -m "feat(voice-streaming): Redis transient audio stream + seq-merged subscribe"
```

---

## Task 5: `DebugEventManager.emit_audio_delta` + buffer wiring

**Files:**
- Modify: `assemblix_api/execution/debug_event_manager.py`
- Test: `tests/unit/test_debug_event_manager_audio.py`

**Interfaces:**
- Consumes: buffer `append_transient` (Tasks 3–4), `AudioDeltaEventData`/`AlignmentData` (Task 1).
- Produces: `DebugEventManager.emit_audio_delta(execution_id, *, step_number, node_id, audio: str, alignment: AlignmentData | None) -> None`.

**Intended test cases (confirm per §0):** `emit_audio_delta` appends an `AUDIO_DELTA` event to the transient ring (a subscriber sees it live); it does NOT go through the retained `append` path; the audio buffer defaults come from settings.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_debug_event_manager_audio.py
from uuid import uuid4

import pytest

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.debug_events import AlignmentData, DebugEventType


@pytest.mark.asyncio
async def test_emit_audio_delta_is_live_transient():
    # Arrange
    mgr = DebugEventManager()
    exec_id = uuid4()
    mgr.open_buffer(exec_id)
    # Act
    await mgr.emit_audio_delta(
        exec_id,
        step_number=2,
        node_id="agent-1",
        audio="QUJD",
        alignment=AlignmentData(chars=["A"], char_start_times_ms=[0], char_durations_ms=[40]),
    )
    got = []
    async for e in mgr.subscribe(exec_id, after_seq=0):
        got.append(e)
        break  # first event only; no terminal is emitted in this test
    # Assert
    assert got[0].event_type == DebugEventType.AUDIO_DELTA
    assert got[0].data["audio"] == "QUJD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_debug_event_manager_audio.py -v`
Expected: FAIL — `AttributeError: 'DebugEventManager' object has no attribute 'emit_audio_delta'`.

- [ ] **Step 3: Implement `emit_audio_delta`**

In `debug_event_manager.py`, import `AlignmentData, AudioDeltaEventData` and add:

```python
    async def emit_audio_delta(
        self,
        execution_id: UUID,
        *,
        step_number: int,
        node_id: str,
        audio: str,
        alignment: AlignmentData | None = None,
    ) -> None:
        """Emit a live-only PCM audio chunk from a streaming voice agent node."""
        event_data = AudioDeltaEventData(
            node_id=node_id, step_number=step_number, audio=audio, alignment=alignment
        )
        event = DebugEvent(
            event_type=DebugEventType.AUDIO_DELTA,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )
        await self._buffer.append_transient(execution_id, event)
```

Wire the audio ring size from settings where the default buffer is constructed in `__init__`:

```python
        if buffer is None:
            from assemblix_api.execution.stream_buffer import InMemoryStreamBuffer

            buffer = InMemoryStreamBuffer(
                audio_max_chunks=get_settings().stream_audio_buffer_max_chunks
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_debug_event_manager_audio.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/execution/debug_event_manager.py tests/unit/test_debug_event_manager_audio.py
git commit -m "feat(voice-streaming): DebugEventManager.emit_audio_delta (transient)"
```

---

## Task 6: Voice catalog — realtime route

**Files:**
- Modify: `assemblix_api/external/voice/base.py`, `assemblix_api/external/voice/models/elevenlabs.json`, `assemblix_api/external/voice/voice_catalog.py`
- Test: `tests/unit/external/test_voice_catalog_realtime.py`

**Interfaces:**
- Consumes: `find_voice_model`, `list_voice_models` (existing).
- Produces: `has_realtime_route(provider: str, model: str) -> bool`; realtime-capable model entries in the catalog.

**Intended test cases (confirm per §0):** `list_voice_models("elevenlabs", "realtime")` returns the seeded realtime models; `has_realtime_route("elevenlabs", "eleven_flash_v2_5")` is True; `has_realtime_route("elevenlabs", "eleven_multilingual_v2")` is False (speech-only); unknown provider → False.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/external/test_voice_catalog_realtime.py
from assemblix_api.external.voice.voice_catalog import has_realtime_route, list_voice_models


def test_realtime_models_are_listed():
    # Arrange / Act
    models = list_voice_models("elevenlabs", "realtime")
    # Assert
    assert any(m.id == "eleven_flash_v2_5" for m in models)
    assert all(m.capability == "realtime" for m in models)


def test_has_realtime_route():
    # Arrange / Act / Assert
    assert has_realtime_route("elevenlabs", "eleven_flash_v2_5") is True
    assert has_realtime_route("elevenlabs", "eleven_multilingual_v2") is False
    assert has_realtime_route("nope", "x") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/external/test_voice_catalog_realtime.py -v`
Expected: FAIL — `ImportError: cannot import name 'has_realtime_route'`.

- [ ] **Step 3: Implement**

In `base.py`, extend the `route` Literal:

```python
    route: Literal["transcription", "completion", "speech", "realtime"]
```

In `models/elevenlabs.json`, add realtime entries (the low-latency models support WS streaming) to the `models` array:

```json
    {
      "id": "eleven_flash_v2_5",
      "label": "Flash v2.5 (realtime)",
      "description": "Realtime low-latency streaming speech.",
      "capability": "realtime",
      "route": "realtime",
      "cost_per_char": 0.000015
    },
    {
      "id": "eleven_turbo_v2_5",
      "label": "Turbo v2.5 (realtime)",
      "description": "Realtime multilingual streaming speech.",
      "capability": "realtime",
      "route": "realtime",
      "cost_per_char": 0.000015
    }
```

> A model id may now appear twice (once `speech`, once `realtime`). `find_voice_model` returns the first match by id — for realtime callers use `has_realtime_route`, which checks capability explicitly. If duplicate ids prove awkward, the spike may instead recommend distinct ids (e.g. suffix), but keeping the same ElevenLabs `model_id` string is required for the WS call, so the JSON keeps the real id and the capability disambiguates.

In `voice_catalog.py`, add:

```python
def has_realtime_route(provider: str, model: str) -> bool:
    """True when (provider, model) is registered as a realtime (WS-streaming) voice model."""
    if provider not in VOICE_PROVIDER_LABELS:
        return False
    return any(m.id == model and m.capability == "realtime" for m in _provider_models(provider))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/external/test_voice_catalog_realtime.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/external/voice/base.py assemblix_api/external/voice/models/elevenlabs.json assemblix_api/external/voice/voice_catalog.py tests/unit/external/test_voice_catalog_realtime.py
git commit -m "feat(voice-streaming): realtime voice route + catalog entries"
```

---

## Task 7: `RealtimeTTSSession` WS client + `mock_tts_ws` seam

**Files:**
- Create: `assemblix_api/external/voice/realtime.py`
- Create: `tests/plugins/tts_ws.py`
- Test: `tests/unit/external/test_realtime_tts_session.py`

**Interfaces:**
- Consumes: `AlignmentData` (Task 1), settings (Task 2).
- Produces:
  - `class RealtimeTTSSession` with `__init__(*, api_key, voice_id, model, on_audio: Callable[[bytes, AlignmentData | None], Awaitable[None]], connect=None, output_format=None, chunk_schedule=None)`, `async def open()`, `async def send_text(text: str)`, `async def flush_and_close() -> int` (returns total chars sent), `async def aclose()`; usable as an async context manager.
  - `on_audio` is invoked once per received audio chunk with `(pcm_bytes, alignment | None)`.
  - `connect` is an injectable async callable returning a websocket-like object (`.send(str)`, `.recv() -> str`, `.close()`); defaults to `websockets.connect`.

**Intended test cases (confirm per §0):** (a) feeding two text chunks then `flush_and_close()` invokes `on_audio` for each scripted audio message with decoded bytes and parsed alignment; (b) `flush_and_close()` returns the total number of characters sent; (c) BOS is sent first and EOS (`{"text": ""}`) last; (d) a WS error during receive stops audio but does not raise out of `send_text` (best-effort) — `flush_and_close()` still returns the chars sent.

- [ ] **Step 1: Write the fake WS seam and the failing test**

```python
# tests/plugins/tts_ws.py
"""Fake ElevenLabs stream-input WS for tests — mirrors mock_llm.

`mock_tts_ws` arms a scripted list of received audio messages (base64 audio +
alignment). The connect factory it returns is injected into RealtimeTTSSession
via its `connect=` argument, so no network is touched.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest


class FakeTTSWebSocket:
    def __init__(self, scripted: list[dict[str, Any]]):
        self.sent: list[dict[str, Any]] = []
        self._scripted = list(scripted)
        self._closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        if self._scripted:
            return json.dumps(self._scripted.pop(0))
        # No more scripted messages: emulate a clean close.
        raise ConnectionClosedOK()

    async def close(self) -> None:
        self._closed = True


class ConnectionClosedOK(Exception):
    """Stand-in for websockets.ConnectionClosedOK in tests."""


class TTSWSMock:
    def __init__(self):
        self.socket: FakeTTSWebSocket | None = None
        self._scripted: list[dict[str, Any]] = []

    def script_audio(self, chunks: list[tuple[bytes, dict | None]]) -> "TTSWSMock":
        """Arm received messages: each (pcm_bytes, alignment_dict|None)."""
        self._scripted = [
            {
                "audio": base64.b64encode(pcm).decode("ascii"),
                "normalizedAlignment": alignment,
                "isFinal": False,
            }
            for pcm, alignment in chunks
        ]
        return self

    async def connect(self, *args: Any, **kwargs: Any) -> FakeTTSWebSocket:
        self.socket = FakeTTSWebSocket(self._scripted)
        return self.socket


@pytest.fixture
def mock_tts_ws() -> TTSWSMock:
    return TTSWSMock()
```

Register the plugin in `tests/conftest.py`'s `pytest_plugins` list alongside `tests.plugins.llm`.

```python
# tests/unit/external/test_realtime_tts_session.py
import pytest

from assemblix_api.external.voice.realtime import RealtimeTTSSession
from assemblix_api.schemas.debug_events import AlignmentData


@pytest.mark.asyncio
async def test_session_streams_audio_and_counts_chars(mock_tts_ws):
    # Arrange
    mock_tts_ws.script_audio(
        [
            (b"\x01\x02", {"chars": ["H"], "char_start_times_ms": [0], "char_durations_ms": [40]}),
            (b"\x03\x04", None),
        ]
    )
    received: list[tuple[bytes, AlignmentData | None]] = []

    async def on_audio(pcm: bytes, alignment: AlignmentData | None) -> None:
        received.append((pcm, alignment))

    session = RealtimeTTSSession(
        api_key="xi-key",
        voice_id="v1",
        model="eleven_flash_v2_5",
        on_audio=on_audio,
        connect=mock_tts_ws.connect,
    )
    # Act
    await session.open()
    await session.send_text("Hello ")
    await session.send_text("world.")
    chars = await session.flush_and_close()
    # Assert
    assert chars == len("Hello ") + len("world.")
    assert [pcm for pcm, _ in received] == [b"\x01\x02", b"\x03\x04"]
    assert received[0][1] == AlignmentData(chars=["H"], char_start_times_ms=[0], char_durations_ms=[40])
    assert mock_tts_ws.socket.sent[0]["text"] == " "  # BOS
    assert mock_tts_ws.socket.sent[-1]["text"] == ""  # EOS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/external/test_realtime_tts_session.py -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_api.external.voice.realtime`.

- [ ] **Step 3: Implement `RealtimeTTSSession`**

Ensure the dep exists: `uv add websockets` (if Task 0 didn't already). Create `assemblix_api/external/voice/realtime.py`:

```python
"""ElevenLabs realtime text-to-speech over the stream-input WebSocket.

Feeds text incrementally (as an agent generates) and forwards PCM audio chunks +
alignment to `on_audio` from a concurrent receive loop. Live/best-effort: a WS error
stops audio but never raises out of send_text — the caller's text stream is unaffected.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable

import structlog

from assemblix_api.core.settings import get_settings
from assemblix_api.schemas.debug_events import AlignmentData

logger = structlog.get_logger(__name__)

OnAudio = Callable[[bytes, AlignmentData | None], Awaitable[None]]


def _parse_alignment(raw: dict | None) -> AlignmentData | None:
    if not raw:
        return None
    # Accept both snake_case and ElevenLabs camelCase (see spike results).
    return AlignmentData(
        chars=raw.get("chars", []),
        char_start_times_ms=raw.get("char_start_times_ms") or raw.get("charStartTimesMs", []),
        char_durations_ms=raw.get("char_durations_ms") or raw.get("charDurationsMs", []),
    )


class RealtimeTTSSession:
    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str,
        model: str,
        on_audio: OnAudio,
        connect: Callable[..., Awaitable] | None = None,
        output_format: str | None = None,
        chunk_schedule: list[int] | None = None,
    ):
        settings = get_settings()
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model
        self._on_audio = on_audio
        self._connect = connect
        self._output_format = output_format or settings.voice_realtime_output_format
        self._chunk_schedule = chunk_schedule or settings.voice_realtime_chunk_schedule
        self._ws_base = settings.elevenlabs_ws_base_url.rstrip("/")
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._chars_sent = 0
        self._failed = False

    async def _default_connect(self, url: str):
        import websockets

        return await websockets.connect(url)

    async def open(self) -> None:
        url = (
            f"{self._ws_base}/text-to-speech/{self._voice_id}/stream-input"
            f"?model_id={self._model}&output_format={self._output_format}"
        )
        connect = self._connect or self._default_connect
        self._ws = await connect(url)
        # BOS: a single space primes the stream; carries voice_settings + xi_api_key.
        await self._ws.send(
            json.dumps(
                {
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                    "generation_config": {"chunk_length_schedule": self._chunk_schedule},
                    "xi_api_key": self._api_key,
                }
            )
        )
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            while True:
                message = await self._ws.recv()
                payload = json.loads(message)
                audio_b64 = payload.get("audio")
                if audio_b64:
                    pcm = base64.b64decode(audio_b64)
                    alignment = _parse_alignment(payload.get("normalizedAlignment"))
                    await self._on_audio(pcm, alignment)
        except Exception as exc:  # noqa: BLE001 — audio is best-effort; log and stop.
            self._failed = True
            logger.info("voice.realtime.recv_stopped", error=str(exc))

    async def send_text(self, text: str) -> None:
        if self._failed or self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"text": text, "try_trigger_generation": True}))
            self._chars_sent += len(text)
        except Exception as exc:  # noqa: BLE001 — best-effort.
            self._failed = True
            logger.info("voice.realtime.send_stopped", error=str(exc))

    async def flush_and_close(self) -> int:
        if self._ws is not None and not self._failed:
            try:
                await self._ws.send(json.dumps({"text": ""}))  # EOS
            except Exception:  # noqa: BLE001
                self._failed = True
        if self._recv_task is not None:
            try:
                await asyncio.wait_for(self._recv_task, timeout=30.0)
            except (TimeoutError, Exception):  # noqa: BLE001
                self._recv_task.cancel()
        await self.aclose()
        return self._chars_sent

    async def aclose(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None

    async def __aenter__(self) -> "RealtimeTTSSession":
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.flush_and_close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/external/test_realtime_tts_session.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/external/voice/realtime.py tests/plugins/tts_ws.py tests/conftest.py tests/unit/external/test_realtime_tts_session.py pyproject.toml uv.lock
git commit -m "feat(voice-streaming): RealtimeTTSSession EL stream-input client + fake WS seam"
```

---

## Task 8: Agent node config — `output_type` + `voice`

**Files:**
- Modify: `assemblix_api/schemas/node.py`
- Test: `tests/unit/test_agent_node_voice_config.py`

**Interfaces:**
- Produces: `AgentNodeConfig.output_type: Literal["text", "voice"] = "text"`; `AgentNodeConfig.voice: VoiceOutputConfig | None = None`; `AgentNode.validate_config()` warnings for misconfigured voice.

**Intended test cases (confirm per §0):** (a) default `output_type == "text"`, `voice is None`; (b) `output_type="voice"` with a full `VoiceOutputConfig` parses; (c) `validate_config` warns when `output_type=="voice"` and no `voice.voice_id`; (d) warns when `output_type=="voice"` + `stream=True` + `response_format=="json_object"` (streaming voice needs text).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_agent_node_voice_config.py
from assemblix_api.enums import AgentProvider
from assemblix_api.nodes.agent_node import AgentNode


def _cfg(**overrides):
    base = {
        "provider": AgentProvider.OPENAI.value,
        "model": "gpt-4o",
        "instructions": [{"role": "system", "content": "hi"}],
    }
    base.update(overrides)
    return {"id": "a1", "type": "agent", "config": base}


def test_voice_defaults_to_text():
    # Arrange / Act
    node = AgentNode(_cfg())
    # Assert
    assert node.typed_config.output_type == "text"
    assert node.typed_config.voice is None


def test_voice_missing_voice_id_warns():
    # Arrange
    node = AgentNode(
        _cfg(output_type="voice", voice={"provider": "elevenlabs", "model": "eleven_flash_v2_5"})
    )
    # Act
    warnings = node.validate_config()
    # Assert
    assert any("voice" in w.lower() for w in warnings)


def test_streaming_voice_json_warns():
    # Arrange
    node = AgentNode(
        _cfg(
            output_type="voice",
            stream=True,
            response_format="json_object",
            voice={"provider": "elevenlabs", "model": "eleven_flash_v2_5", "voice_id": "v1"},
        )
    )
    # Act
    warnings = node.validate_config()
    # Assert
    assert any("text" in w.lower() for w in warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_agent_node_voice_config.py -v`
Expected: FAIL — `output_type` not a field / no such warning.

- [ ] **Step 3: Implement config + warnings**

In `assemblix_api/schemas/node.py`, add to `AgentNodeConfig` (after `stream`):

```python
    # Output modality. "text" (default) unchanged; "voice" streams realtime audio when the
    # run streams and a realtime model is set, else synthesizes one buffered base64 blob.
    output_type: Literal["text", "voice"] = "text"
    voice: VoiceOutputConfig | None = None
```

In `assemblix_api/nodes/agent_node.py::validate_config`, before `return errors`:

```python
        if self.typed_config.output_type == "voice":
            voice = self.typed_config.voice
            if voice is None or not voice.voice_id or not voice.model:
                errors.append("Voice output is enabled but no voice is fully selected")
            if self.typed_config.stream and self.typed_config.response_format == "json_object":
                errors.append(
                    "Streaming voice needs text output; set response_format=text or it runs buffered"
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_agent_node_voice_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/schemas/node.py assemblix_api/nodes/agent_node.py tests/unit/test_agent_node_voice_config.py
git commit -m "feat(voice-streaming): AgentNodeConfig output_type + voice + validation"
```

---

## Task 9: `NodeInput.on_audio` + node_runner audio sink

**Files:**
- Modify: `assemblix_api/schemas/execution.py`, `assemblix_api/execution/node_runner.py`
- Test: `tests/unit/test_node_runner_audio_sink.py`

**Interfaces:**
- Consumes: `emit_audio_delta` (Task 5).
- Produces: `NodeInput.on_audio: Callable[[bytes, AlignmentData | None], Awaitable[None]] | None`; `NodeRunner.run` sets it (base64-encoding PCM and forwarding to `emit_audio_delta`) under the same streaming condition as `on_delta`.

**Intended test cases (confirm per §0):** on a streaming run, `NodeRunner.run` sets `node_input.on_audio`, and calling it with PCM bytes + alignment invokes `emit_audio_delta` with the base64 of those bytes and the right `node_id`/`step_number`; on a non-streaming run `on_audio` stays None.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_node_runner_audio_sink.py
import base64
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from assemblix_api.schemas.debug_events import AlignmentData


@pytest.mark.asyncio
async def test_audio_sink_forwards_to_emit_audio_delta(make_streaming_node_runner):
    # Arrange — helper builds (runner, debug_event_manager, node_input, node) for a streaming run
    runner, dem, node_input, node, exec_id = make_streaming_node_runner()
    dem.emit_audio_delta = AsyncMock()
    captured = {}

    async def _capture(_ni):
        captured["on_audio"] = _ni.on_audio
        return node_input_output_stub()

    node.execute = _capture
    # Act
    await runner.run(node, node_input, node_id="agent-1", step_number=4)
    await captured["on_audio"](b"\x09\x08", AlignmentData(chars=["x"], char_start_times_ms=[0], char_durations_ms=[10]))
    # Assert
    dem.emit_audio_delta.assert_awaited_once()
    kwargs = dem.emit_audio_delta.await_args.kwargs
    assert kwargs["node_id"] == "agent-1"
    assert kwargs["step_number"] == 4
    assert kwargs["audio"] == base64.b64encode(b"\x09\x08").decode("ascii")
```

> Use the existing streaming node-runner test fixtures/helpers from `tests/unit/nodes/test_agent_node_stream_gate.py` / the 2a node-runner tests as the model for `make_streaming_node_runner` and `node_input_output_stub`; if none exists, inline the `ExecutionContext(stream_enabled=True, ...)` + `DebugEventManager` setup that those tests already use (copy their Arrange block).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_node_runner_audio_sink.py -v`
Expected: FAIL — `NodeInput` has no `on_audio` / sink not set.

- [ ] **Step 3: Implement**

In `assemblix_api/schemas/execution.py`, add to `NodeInput` (after `on_delta`), and import `AlignmentData` under `TYPE_CHECKING`:

```python
    # Per-run PCM audio sink for streaming voice; set by NodeRunner alongside on_delta.
    on_audio: Callable[[bytes, "AlignmentData | None"], Awaitable[None]] | None = None
```

In `assemblix_api/execution/node_runner.py::run`, inside the existing `if ctx.stream_enabled and ...:` block, add the audio sink next to `_sink`:

```python
            import base64

            async def _audio_sink(pcm: bytes, alignment) -> None:
                await self._debug_event_manager.emit_audio_delta(
                    execution_id,
                    step_number=step_number,
                    node_id=node_id,
                    audio=base64.b64encode(pcm).decode("ascii"),
                    alignment=alignment,
                )

            node_input.on_audio = _audio_sink
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_node_runner_audio_sink.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/schemas/execution.py assemblix_api/execution/node_runner.py tests/unit/test_node_runner_audio_sink.py
git commit -m "feat(voice-streaming): NodeInput.on_audio + node_runner PCM sink"
```

---

## Task 10: Agent voice orchestration helper

**Files:**
- Create: `assemblix_api/nodes/agent_voice.py`
- Test: `tests/unit/nodes/test_agent_voice_helper.py`

**Interfaces:**
- Consumes: `RealtimeTTSSession` (Task 7), `has_realtime_route` (Task 6), `synthesize` (`external/voice/synthesis.py`), `compute_tts_cost` (`external/voice/pricing.py`), `get_voice_api_key_with_fallback`.
- Produces:
  - `should_stream_voice(cfg, on_delta, on_audio) -> bool` — the five-condition live gate (request/node stream already folded into `on_delta`/`on_audio` presence + text format).
  - `async open_voice_session(cfg, context, on_delta, on_audio) -> tuple[RealtimeTTSSession, Callable]` — resolves the credential, opens the session, returns `(session, tee_on_delta)` where `tee_on_delta` wraps the original `on_delta` to also feed the WS.
  - `voice_cost_metadata(cfg, chars, is_system_key) -> dict` — the `{cost, cost_kind, used_system_key, chars, voice_provider, voice_model}` facts.
  - `async synthesize_buffered(cfg, context, text) -> tuple[dict, dict]` — buffered base64 path (returns `(audio_dict, cost_metadata)`), the migrated phase-1 logic under a char cap.

**Intended test cases (confirm per §0):** (a) `should_stream_voice` True only when output_type=voice + voice complete + realtime model + both sinks present; (b) `open_voice_session` returns a tee that calls the original on_delta AND `session.send_text`; (c) `voice_cost_metadata` yields `cost_kind="voice"` and `cost = compute_tts_cost(...)`; (d) `synthesize_buffered` returns audio+cost under the cap and `({}, {})`-style skip (no audio) over the cap.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/nodes/test_agent_voice_helper.py
import pytest

from assemblix_api.nodes import agent_voice
from assemblix_api.schemas.node import AgentNodeConfig, VoiceOutputConfig


def _voice_cfg():
    return AgentNodeConfig(
        provider="openai",
        model="gpt-4o",
        instructions=[{"role": "system", "content": "x"}],
        output_type="voice",
        stream=True,
        voice=VoiceOutputConfig(
            provider="elevenlabs", model="eleven_flash_v2_5", voice_id="v1"
        ),
    )


async def _noop(_x):
    pass


async def _noop_audio(_p, _a):
    pass


def test_should_stream_voice_requires_all_conditions():
    # Arrange
    cfg = _voice_cfg()
    # Act / Assert
    assert agent_voice.should_stream_voice(cfg, on_delta=_noop, on_audio=_noop_audio) is True
    assert agent_voice.should_stream_voice(cfg, on_delta=None, on_audio=_noop_audio) is False
    text_cfg = cfg.model_copy(update={"output_type": "text"})
    assert agent_voice.should_stream_voice(text_cfg, on_delta=_noop, on_audio=_noop_audio) is False


def test_voice_cost_metadata():
    # Arrange
    cfg = _voice_cfg()
    # Act
    meta = agent_voice.voice_cost_metadata(cfg, chars=100, is_system_key=True)
    # Assert
    assert meta["cost_kind"] == "voice"
    assert meta["used_system_key"] is True
    assert meta["chars"] == 100
    assert meta["voice_model"] == "eleven_flash_v2_5"
    assert meta["cost"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/nodes/test_agent_voice_helper.py -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_api.nodes.agent_voice`.

- [ ] **Step 3: Implement the helper**

```python
# assemblix_api/nodes/agent_voice.py
"""Voice orchestration for the agent node — kept out of agent_node.execute to stay lean.

Two mutually exclusive paths per run: a live realtime WS session (streaming) or one
buffered base64 synthesis (non-streaming). END has no synthesis, so this is the only
place TTS happens — a double call is structurally impossible.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from uuid import UUID

from assemblix_api.core.settings import get_settings
from assemblix_api.external.voice.pricing import compute_tts_cost
from assemblix_api.external.voice.realtime import RealtimeTTSSession
from assemblix_api.external.voice.synthesis import synthesize
from assemblix_api.external.voice.voice_catalog import has_realtime_route
from assemblix_api.schemas.execution import ExecutionContext
from assemblix_api.schemas.node import AgentNodeConfig

OnDelta = Callable[[str], Awaitable[None]]
OnAudio = Callable[..., Awaitable[None]]


def _voice_ready(cfg: AgentNodeConfig) -> bool:
    v = cfg.voice
    return bool(cfg.output_type == "voice" and v and v.voice_id and v.model and v.provider)


def should_stream_voice(
    cfg: AgentNodeConfig, *, on_delta: OnDelta | None, on_audio: OnAudio | None
) -> bool:
    """Live-audio gate: voice-ready, realtime model, and both sinks present (which already
    encode request.stream × node.stream × text-format from the caller)."""
    if not _voice_ready(cfg) or on_delta is None or on_audio is None:
        return False
    assert cfg.voice is not None
    return has_realtime_route(cfg.voice.provider, cfg.voice.model)


async def _resolve_key(cfg: AgentNodeConfig, context: ExecutionContext) -> tuple[str, bool]:
    assert context.credential_service is not None
    assert context.organization_plan is not None
    v = cfg.voice
    assert v is not None
    return await context.credential_service.get_voice_api_key_with_fallback(
        credentials_id=UUID(v.credential_id) if v.credential_id else None,
        project_id=context.project_id,
        voice_provider=v.provider,
        organization_plan=context.organization_plan,
    )


async def open_voice_session(
    cfg: AgentNodeConfig,
    context: ExecutionContext,
    *,
    on_delta: OnDelta,
    on_audio: OnAudio,
) -> tuple[RealtimeTTSSession, OnDelta, bool]:
    """Open a live WS session; return (session, tee_on_delta, is_system_key)."""
    assert cfg.voice is not None
    api_key, is_system_key = await _resolve_key(cfg, context)
    session = RealtimeTTSSession(
        api_key=api_key,
        voice_id=cfg.voice.voice_id,  # type: ignore[arg-type]
        model=cfg.voice.model,
        on_audio=on_audio,
    )
    await session.open()

    async def tee(text: str) -> None:
        await on_delta(text)
        await session.send_text(text)

    return session, tee, is_system_key


def voice_cost_metadata(cfg: AgentNodeConfig, *, chars: int, is_system_key: bool) -> dict:
    assert cfg.voice is not None
    cost = compute_tts_cost(cfg.voice.provider, cfg.voice.model, chars)
    return {
        "cost": float(cost),
        "cost_kind": "voice",
        "used_system_key": is_system_key,
        "chars": chars,
        "voice_provider": cfg.voice.provider,
        "voice_model": cfg.voice.model,
    }


async def synthesize_buffered(
    cfg: AgentNodeConfig, context: ExecutionContext, text: str
) -> tuple[dict | None, dict]:
    """Non-streaming path: one base64 synthesis under the char cap. Returns
    (audio_dict|None, cost_metadata). Over the cap or empty text → (None, {})."""
    assert cfg.voice is not None
    limit = get_settings().voice_output_max_chars
    if not text or len(text) > limit or not cfg.voice.voice_id:
        return None, {}
    api_key, is_system_key = await _resolve_key(cfg, context)
    result = await synthesize(
        text=text,
        provider=cfg.voice.provider,
        model=cfg.voice.model,
        voice_id=cfg.voice.voice_id,
        api_key=api_key,
    )
    audio = {
        "base64": base64.b64encode(result.audio_bytes).decode("ascii"),
        "format": "mp3",
        "voiceId": cfg.voice.voice_id,
        "model": cfg.voice.model,
    }
    return audio, voice_cost_metadata(cfg, chars=result.chars, is_system_key=is_system_key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/nodes/test_agent_voice_helper.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/nodes/agent_voice.py tests/unit/nodes/test_agent_voice_helper.py
git commit -m "feat(voice-streaming): agent voice helper (live gate, tee, buffered fallback, cost)"
```

---

## Task 11: Wire voice into `AgentNode.execute`

**Files:**
- Modify: `assemblix_api/nodes/agent_node.py`
- Test: `tests/unit/nodes/test_agent_node_voice_execute.py`

**Interfaces:**
- Consumes: `agent_voice.should_stream_voice`, `open_voice_session`, `voice_cost_metadata`, `synthesize_buffered` (Task 10); `node_input.on_delta` / `node_input.on_audio` (Task 9).

**Intended test cases (confirm per §0):** (a) **live path** — when `should_stream_voice` holds, `execute` opens a session, tees deltas (text deltas still emit AND `send_text` is called), calls `flush_and_close`, and attaches voice cost metadata to the output; no `data["audio"]` base64 is set. (b) **buffered path** — output_type=voice but non-streaming (`on_delta`/`on_audio` None) → `data["audio"].base64` present and cost metadata attached, exactly one synth call. (c) **text path** — output_type=text → no voice, output unchanged. (d) a WS failure mid-run does not fail the run (audio best-effort).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/nodes/test_agent_node_voice_execute.py
import pytest

# Reuse the agent-node execute test scaffolding from the existing
# tests/unit/nodes/test_agent_node*.py (same NodeInput/ExecutionContext + mock_llm setup).


@pytest.mark.asyncio
async def test_live_voice_tees_and_meters(mock_llm, mock_tts_ws, make_agent_node_input):
    # Arrange
    mock_llm.set_stream(["Hello ", "world."])
    mock_tts_ws.script_audio([(b"\x01", None)])
    node, node_input = make_agent_node_input(
        output_type="voice",
        stream=True,
        voice={"provider": "elevenlabs", "model": "eleven_flash_v2_5", "voice_id": "v1"},
        streaming_run=True,  # sets on_delta + on_audio sinks + stream_enabled
        tts_connect=mock_tts_ws.connect,
    )
    # Act
    out = await node.execute(node_input)
    # Assert — metered as voice, no base64 blob on a live run
    assert out.metadata["cost_kind"] == "voice"
    assert "audio" not in out.data
    assert mock_tts_ws.socket.sent[-1]["text"] == ""  # EOS sent


@pytest.mark.asyncio
async def test_buffered_voice_single_synthesis(mock_llm, make_agent_node_input, mocker):
    # Arrange
    mock_llm.set_response("Hi there")
    synth = mocker.patch(
        "assemblix_api.nodes.agent_voice.synthesize",
        return_value=_synthesis_result(b"MP3", chars=8),
    )
    node, node_input = make_agent_node_input(
        output_type="voice",
        stream=False,
        voice={"provider": "elevenlabs", "model": "eleven_multilingual_v2", "voice_id": "v1"},
        streaming_run=False,
    )
    # Act
    out = await node.execute(node_input)
    # Assert
    assert out.data["audio"]["format"] == "mp3"
    assert out.metadata["cost_kind"] == "voice"
    synth.assert_awaited_once()
```

> `make_agent_node_input` and `_synthesis_result` follow the existing agent-node test builders; `tts_connect` must be injected into the session the node opens (see Step 3 — allow a test hook). If the existing builders don't accept these, extend them minimally in the test file's Arrange block by constructing `ExecutionContext`/`NodeInput` directly as the 2a agent-node tests do.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/nodes/test_agent_node_voice_execute.py -v`
Expected: FAIL — no voice handling in `execute`.

- [ ] **Step 3: Implement wiring in `execute`**

In `assemblix_api/nodes/agent_node.py`, add `from assemblix_api.nodes import agent_voice`. Replace the streaming section (around line 135-148) so voice is orchestrated around the `AgentRunner().run` call:

```python
            on_delta = node_input.on_delta if (cfg.stream and not parse_json) else None
            on_audio = node_input.on_audio

            tts_session = None
            voice_is_system_key = False
            effective_on_delta = on_delta
            if on_delta is not None and agent_voice.should_stream_voice(
                cfg, on_delta=on_delta, on_audio=on_audio
            ):
                tts_session, effective_on_delta, voice_is_system_key = (
                    await agent_voice.open_voice_session(
                        cfg, context, on_delta=on_delta, on_audio=on_audio
                    )
                )

            result = await AgentRunner().run(
                model=model,
                provider=cfg.provider.value,
                model_name=cfg.model,
                instructions=instructions or None,
                conversation=conversation,
                toolsets=toolsets,
                parse_json=parse_json,
                total_timeout=total_timeout,
                on_delta=effective_on_delta,
            )

        output_data = {
            "message": result.content,
            "parsed_message": result.parsed_content,
            "tool_executions": result.tool_executions,
        }
        extra_metadata: dict = {}

        # Live voice: drain the WS and meter the synthesized chars. No base64 on a live run.
        if tts_session is not None:
            chars = await tts_session.flush_and_close()
            if chars > 0:
                extra_metadata = agent_voice.voice_cost_metadata(
                    cfg, chars=chars, is_system_key=voice_is_system_key
                )
        # Buffered voice: exactly one synthesis when voice is requested but not streamed live.
        elif cfg.output_type == "voice" and cfg.voice and cfg.voice.voice_id:
            audio, cost_meta = await agent_voice.synthesize_buffered(cfg, context, result.content)
            if audio is not None:
                output_data["audio"] = audio
                extra_metadata = cost_meta

        return NodeOutput(
            data=output_data,
            metadata={
                **result.metadata,
                **extra_metadata,
                "model": cfg.model,
                "provider": cfg.provider.value,
                "used_system_key": is_system_key,
                "llm_request": messages,
            },
            history_append=self._build_history_append(result),
        )
```

Delete the old trailing `return NodeOutput(...)` block that this replaces (the one at lines ~150-166). For the test hook in Step 1 (`tts_connect`), thread an optional `connect` into `open_voice_session` only if the existing test builders need it; otherwise the fake WS is injected by patching `assemblix_api.nodes.agent_voice.RealtimeTTSSession` in the test. Prefer patching in the test to keep production signatures clean:

```python
# In test Arrange instead of tts_connect:
mocker.patch(
    "assemblix_api.nodes.agent_voice.RealtimeTTSSession",
    lambda **kw: RealtimeTTSSession(**{**kw, "connect": mock_tts_ws.connect}),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/nodes/test_agent_node_voice_execute.py tests/unit/nodes/test_agent_node_stream_gate.py -v`
Expected: PASS (new voice tests pass; the 2a text-stream gate tests still pass — text-only behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/nodes/agent_node.py tests/unit/nodes/test_agent_node_voice_execute.py
git commit -m "feat(voice-streaming): wire live + buffered voice into AgentNode.execute"
```

---

## Task 12: Remove synthesis from the END node

**Files:**
- Modify: `assemblix_api/nodes/end_node.py`, `assemblix_api/schemas/node.py`
- Test: `tests/unit/nodes/test_end_node_no_synthesis.py`; update `tests/unit/nodes/test_end_node_voice.py`

**Interfaces:**
- Produces: `EndNodeConfig` without `output_format`/`voice`/`voice_max_chars`; `EndNode.execute` with no synthesis; agent audio (buffered) passes through via `output_mode="last_agent"`.

**Intended test cases (confirm per §0):** (a) END with `output_mode="last_agent"` returns the last agent's output verbatim, including any `audio` the agent attached, without calling `synthesize`; (b) `EndNodeConfig` no longer accepts voice fields (extra keys are ignored, not errors — a legacy config with `output_format: "voice"` parses and produces plain text output); (c) `EndNode` has no `_synthesize_into` attribute.

- [ ] **Step 1: Write the failing test + retire the old END-voice test**

```python
# tests/unit/nodes/test_end_node_no_synthesis.py
import pytest

from assemblix_api.nodes.end_node import EndNode
from assemblix_api.schemas.node import EndNodeConfig


def test_end_node_has_no_synthesis():
    # Arrange / Act / Assert
    assert not hasattr(EndNode, "_synthesize_into")


def test_legacy_voice_config_is_ignored():
    # Arrange / Act — legacy keys must not raise; they are simply dropped.
    cfg = EndNodeConfig(**{"output_mode": "last_agent", "output_format": "voice", "voice": {"provider": "elevenlabs", "model": "m"}})
    # Assert
    assert not hasattr(cfg, "output_format")
```

Delete `tests/unit/nodes/test_end_node_voice.py` (its behavior moved to the agent-node tests in Tasks 10–11). Note the deletion in the commit body.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/nodes/test_end_node_no_synthesis.py -v`
Expected: FAIL — `_synthesize_into` still exists.

- [ ] **Step 3: Implement removal**

In `assemblix_api/schemas/node.py::EndNodeConfig`, delete the three voice fields:

```python
    # (removed) output_format / voice / voice_max_chars — voice moved to the AGENT node.
```

Confirm `DTOModel`/pydantic drops unknown keys (default `extra="ignore"`); if the base sets `extra="forbid"`, add `model_config = ConfigDict(extra="ignore")` to `EndNodeConfig` so legacy graphs still load.

In `assemblix_api/nodes/end_node.py`: delete `_synthesize_into`, the `import base64`, the `from ...pricing import compute_tts_cost`, the `from ...synthesis import synthesize`, the `from uuid import UUID` (if now unused), the voice branch in `execute` (the `if self.typed_config.output_format == "voice"...` block), and the voice branch in `validate_config`. The END node returns to its pre-phase-1 shape plus the state/session/error handling it already had.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/nodes/test_end_node_no_synthesis.py tests/unit/nodes/ -v`
Expected: PASS. Then run the broader suite to catch fallout: `pytest tests/unit/ -q`.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/nodes/end_node.py assemblix_api/schemas/node.py tests/unit/nodes/test_end_node_no_synthesis.py
git rm tests/unit/nodes/test_end_node_voice.py
git commit -m "refactor(voice-streaming): remove synthesis from END (moved to agent)"
```

---

## Task 13: Integration — streaming voice e2e + no-double-call

**Files:**
- Test: `tests/integration/test_streaming_voice_e2e.py`

**Interfaces:**
- Consumes: the full stack (agent node, buffer, SSE endpoint, `mock_llm`, `mock_tts_ws`).

**Intended test cases (confirm per §0):** (a) a workflow START→AGENT(voice,stream,realtime)→END dispatched with `stream=true` produces `AUDIO_DELTA` events on `GET /executions/{id}/stream`, interleaved with `STREAM_DELTA`, all before the agent's `step_complete`; (b) the same workflow dispatched with `stream=false` produces zero `AUDIO_DELTA` and one buffered `audio.base64` in the final output (no double synthesis — assert `synthesize` called exactly once and the WS never opened); (c) a mid-stream WS failure yields text + partial audio and a successful (not FAILED) run.

- [ ] **Step 1: Write the failing test**

Model it on `tests/integration/test_streaming_e2e.py` and `tests/integration/test_execution_stream_endpoint.py`. Arrange a workflow with an agent node `output_type="voice"`, `stream=True`, a realtime voice; arm `mock_llm.set_stream([...])` and `mock_tts_ws.script_audio([...])`; patch `assemblix_api.nodes.agent_voice.RealtimeTTSSession` to inject `mock_tts_ws.connect`. Act: POST `execute/debug {stream:true}` and read the SSE. Assert the event-type sequence and ordering.

```python
@pytest.mark.asyncio
async def test_streaming_voice_emits_audio_before_step_complete(client, mock_llm, mock_tts_ws, mocker, seed_voice_workflow):
    # Arrange
    mock_llm.set_stream(["Hi ", "there."])
    mock_tts_ws.script_audio([(b"\x01\x02", None), (b"\x03\x04", None)])
    mocker.patch(
        "assemblix_api.nodes.agent_voice.RealtimeTTSSession",
        lambda **kw: _RealtimeTTSSession(**{**kw, "connect": mock_tts_ws.connect}),
    )
    workflow_id = await seed_voice_workflow(stream=True)
    # Act
    events = await _collect_sse(client, workflow_id, stream=True)
    # Assert
    types = [e["event"] for e in events]
    assert "audio_delta" in types
    agent_complete = next(i for i, e in enumerate(events) if e["event"] == "step_complete" and e["data"]["nodeType"] == "agent")
    last_audio = max(i for i, e in enumerate(events) if e["event"] == "audio_delta")
    assert last_audio < agent_complete  # all audio precedes the agent's step_complete


@pytest.mark.asyncio
async def test_non_streaming_voice_single_synthesis(client, mock_llm, mocker, seed_voice_workflow):
    # Arrange
    mock_llm.set_response("Hi there.")
    synth = mocker.patch("assemblix_api.nodes.agent_voice.synthesize", return_value=_synthesis_result(b"MP3", 9))
    ws = mocker.patch("assemblix_api.nodes.agent_voice.RealtimeTTSSession")
    workflow_id = await seed_voice_workflow(stream=False)
    # Act
    result = await _run_task(client, workflow_id, stream=False)
    # Assert
    assert result["output"]["audio"]["format"] == "mp3"
    synth.assert_awaited_once()
    ws.assert_not_called()  # no double synthesis, WS never opened
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_streaming_voice_e2e.py -v`
Expected: FAIL initially (helpers/seed not present) → build the `seed_voice_workflow`, `_collect_sse`, `_run_task` helpers from the existing integration test patterns, then the assertions drive any remaining wiring fixes.

- [ ] **Step 3: Make it pass**

No new production code should be needed if Tasks 1–12 are correct; if an assertion fails, fix the responsible unit (do not weaken the assertion). Common fixes: ensure `node_runner` sets `on_audio` before agent execution; ensure `step_complete` for the agent is emitted after `flush_and_close`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_streaming_voice_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_streaming_voice_e2e.py
git commit -m "test(voice-streaming): e2e realtime audio ordering + no-double-synthesis"
```

---

## Task 14: Backend gate — full suite + lint/type

**Files:** none (verification task).

- [ ] **Step 1: Run the full backend gate**

Run: `source .venv/bin/activate && make check` (ruff + mypy + pytest+coverage). Expected: all green. Fix any ruff/mypy issues introduced (e.g. the local `import base64` in `node_runner.run` should move to module top; `import websockets` inside `_default_connect` is intentional to keep it optional).

- [ ] **Step 2: Commit any lint/type fixes**

```bash
git add -A
git commit -m "style(voice-streaming): ruff + mypy clean-up"
```

---

## Task 15: Frontend types

**Files:**
- Modify: `src/entities/workflow/model/types.ts`

- [ ] **Step 1: Update the types**

In `AgentNodeConfig` (around line 74-119) add:

```ts
  /** Output modality. "voice" streams realtime audio when the run streams + a realtime model is set. */
  outputType?: "text" | "voice";
  /** TTS voice for this agent (provider is a plain voice-provider id, not the LLM Provider enum). */
  voice?: VoiceOutputConfig;
```

In `EndNodeConfig` (around line 163-193) **remove** `outputFormat`, `voice`, and `voiceMaxChars`. Keep `VoiceOutputConfig` (now referenced by `AgentNodeConfig`).

- [ ] **Step 2: Type-check**

Run: `cd assemblix-app-web && yarn build`
Expected: build succeeds, OR surfaces every call site that reads `endConfig.voice` / `outputFormat` (the end-node form — fixed in Task 16).

- [ ] **Step 3: Commit**

```bash
git add src/entities/workflow/model/types.ts
git commit -m "feat(voice-streaming): move voice config from End to Agent in FE types"
```

---

## Task 16: Frontend forms — move the voice picker to the agent

**Files:**
- Modify: `src/entities/workflow/lib/workflow-editor/ui/node-forms/agent-node-form.tsx`, `end-node-form.tsx`

- [ ] **Step 1: Add output-type + voice picker to the agent form**

In `agent-node-form.tsx`, near the existing Stream toggle (line ~811), add an **Output** select (`text | voice`) bound to `config.outputType` via a new `handleOutputTypeChange`. When `outputType === "voice"`, render the voice-picker cascade **copied from `end-node-form.tsx` (lines 493-716)** but: use `capability: "realtime"` in `useGetVoiceProvidersQuery`/`useGetVoiceProviderModelsQuery`, bind to `config.voice` (`VoiceOutputConfig`), and reuse `useGetCredentialVoicesQuery`/`useGetSystemVoicesQuery` unchanged. Keep the "Stream output" toggle; realtime voice needs `stream=true`, so show a hint when `outputType==="voice" && !config.stream`.

- [ ] **Step 2: Remove the voice picker from the end form**

In `end-node-form.tsx`, delete the output-format select and the entire voice cascade (lines ~171-221 handlers + ~493-716 JSX + the `@/entities/voice-model` imports now unused). The end form returns to output-mode / filters / flags only.

- [ ] **Step 3: Type-check + dogfood**

Run: `cd assemblix-app-web && yarn build` → succeeds. Then dogfood: start the stack, open the editor, confirm the agent node shows Output=text/voice with the realtime voice picker and the end node no longer shows voice.

- [ ] **Step 4: Commit**

```bash
git add src/entities/workflow/lib/workflow-editor/ui/node-forms/agent-node-form.tsx src/entities/workflow/lib/workflow-editor/ui/node-forms/end-node-form.tsx
git commit -m "feat(voice-streaming): agent-node voice picker (realtime); drop end-node voice UI"
```

---

## Task 17: Frontend — Web Audio PCM player + audio_delta wiring

**Files:**
- Create: `src/entities/workflow/lib/workflow-editor/lib/use-pcm-player.ts`
- Modify: `src/entities/workflow/lib/workflow-editor/lib/use-workflow-debug.ts`, `ui/debug/execution-viewer.tsx`

- [ ] **Step 1: Implement the streaming PCM player**

Create `use-pcm-player.ts` — a hook exposing `pushChunk(base64Pcm: string)` and `reset()`. It lazily creates one `AudioContext`, decodes base64 → `Int16Array` → `Float32Array` (`sample / 32768`), builds a mono 16000 Hz `AudioBuffer`, and schedules an `AudioBufferSourceNode` at a running `nextStartTime` cursor (`Math.max(ctx.currentTime, nextStartTime)`), advancing the cursor by `buffer.duration` for gapless playback (approach validated in Task 0):

```ts
export function usePcmPlayer(sampleRate = 16000) {
  const ctxRef = useRef<AudioContext | null>(null);
  const nextStartRef = useRef(0);

  const pushChunk = useCallback((base64Pcm: string) => {
    const ctx = (ctxRef.current ??= new AudioContext({ sampleRate }));
    const bytes = Uint8Array.from(atob(base64Pcm), (c) => c.charCodeAt(0));
    const pcm16 = new Int16Array(bytes.buffer);
    const f32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) f32[i] = pcm16[i] / 32768;
    const buffer = ctx.createBuffer(1, f32.length, sampleRate);
    buffer.copyToChannel(f32, 0);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    const startAt = Math.max(ctx.currentTime, nextStartRef.current);
    src.start(startAt);
    nextStartRef.current = startAt + buffer.duration;
  }, [sampleRate]);

  const reset = useCallback(() => {
    nextStartRef.current = 0;
  }, []);

  return { pushChunk, reset };
}
```

- [ ] **Step 2: Wire `audio_delta` into the debug consumer**

In `use-workflow-debug.ts`, where `consumeStream` switches on `event_type`, add a branch: on `"audio_delta"`, call `pcmPlayer.pushChunk(event.data.audio)` (thread the `usePcmPlayer` handle into the hook, or expose an `onAudioDelta` callback the panel wires to the player). Reset the player on `execution_started`. In `execution-viewer.tsx`, keep the existing `execution_complete` base64 `<audio>` fallback for non-streaming voice runs (buffered path) — a live run has no final `audio.base64`, so that element simply doesn't render.

- [ ] **Step 3: Type-check + dogfood**

Run: `cd assemblix-app-web && yarn build` → succeeds. Dogfood: run a streaming voice workflow from the debug panel with the Streaming toggle on; confirm audio plays progressively as tokens stream; run with the toggle off and confirm the buffered `<audio>` still plays the final clip.

- [ ] **Step 4: Commit**

```bash
git add src/entities/workflow/lib/workflow-editor/lib/use-pcm-player.ts src/entities/workflow/lib/workflow-editor/lib/use-workflow-debug.ts src/entities/workflow/lib/workflow-editor/ui/debug/execution-viewer.tsx
git commit -m "feat(voice-streaming): Web Audio PCM player + audio_delta wiring in debug runner"
```

---

## Self-Review (completed by the plan author)

**Spec coverage:**
- §3 realtime WS client → Task 7. Catalog `capability:"realtime"` → Task 6. Agent `output_type`/`voice` → Task 8. Realtime coordinator/tee → Tasks 9–11. `AUDIO_DELTA`+alignment → Task 1. Transient retention (in-memory + Redis) → Tasks 3–4. `emit_audio_delta` → Task 5. END migration → Task 12. Buffered fallback moved to agent → Task 10–11. Debug player → Task 17. Fake EL WS seam → Task 7. Settings → Task 2. Metering → uses existing accumulator; agent emits facts (Tasks 10–11); no billing task needed (confirmed `cost_accumulator.py`/`credit_service.py` already handle `cost_kind="voice"`/`VOICE_USAGE`). §4.5 Redis-optional → Tasks 3 (in-memory default) + 4 (Redis). §7 error handling → best-effort in `RealtimeTTSSession` (Task 7) + integration case (Task 13c). Ordering guarantee → Task 13a.
- **Open items from spec §11 folded in:** WS lib choice + protocol → Task 0 spike; char-ceiling on the streaming path → currently NOT capped for live (only buffered path caps, Task 10); multiple voiced agents → allowed (each agent owns its session — no constraint added). These two remain product calls; they are flagged, not silently dropped. **Confirm with the user during Task 0/8** whether live streaming voice needs a char ceiling.

**Placeholder scan:** No "TBD"/"add error handling" left. Test-helper reuse (`make_agent_node_input`, `seed_voice_workflow`) points at concrete existing patterns with instructions to inline if absent — acceptable because the referenced 2a/phase-1 tests exist.

**Type consistency:** `on_audio: Callable[[bytes, AlignmentData | None], Awaitable[None]]` consistent across `NodeInput` (Task 9), `RealtimeTTSSession` (Task 7), `emit_audio_delta` (Task 5, takes `audio: str` after base64). `AudioDeltaEventData.audio: str` (base64) — node_runner encodes bytes→str (Task 9). `has_realtime_route` used in Tasks 6 + 10. `voice_cost_metadata`/`synthesize_buffered` signatures match their call sites in Task 11.

**Known follow-ups (not blockers):** live-run audio is not persisted (by design); frontend reconnect-by-cursor for text inherits 2a's single-fetch limitation; char-ceiling on live path is open (above).
