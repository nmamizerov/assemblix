# Streaming voice output (realtime agent→TTS, debug-first) — Design

- **Date:** 2026-07-07
- **Status:** Approved design (pre-implementation)
- **Sub-project:** 2b of 3 in the "conversational voice + avatars" initiative
- **Author:** design session (brainstorming)

## 1. Context and the larger initiative

Assemblix is a visual workflow/agent platform; a chat turn is a workflow execution. The
initiative to make it a strong multi-modal chat product decomposes into three sequential
sub-projects, each building on the previous:

| #      | Sub-project                                                        | Depends on                 |
| ------ | ------------------------------------------------------------------ | -------------------------- |
| 1      | Voice output on the END node (ElevenLabs, non-streaming) — **done** | the `external/voice/` seam |
| 2a     | Streaming of text tokens — **done, merged (PR #18)**               | #1                         |
| **2b** | **Streaming of audio chunks (realtime agent→TTS) — this spec**     | #2a                        |
| 3      | AI avatars (real-time lip-sync)                                    | #2b                        |

Phase 2a shipped the streaming **mechanism**: a per-execution sequence-numbered replayable
event buffer (`execution/stream_buffer.py`, in-memory deque + Redis Stream), a `STREAM_DELTA`
event carrying an agent's text tokens, and a subscribe-by-id SSE endpoint
`GET /api/executions/{id}/stream` (cursor replay + live tail). Text tokens flow via
pydantic-ai's `event_stream_handler` → the agent node's `on_delta` sink → `emit_stream_delta`.
Phase 1 shipped voice on the END node: it synthesizes the whole final text into base64 mp3,
inline in the node output, metered per character, never persisted.

**This spec (2b) makes voice output stream in real time**, so audio begins *while the agent is
still generating text*. That latency profile — and native character-level alignment — is what
phase 3 (avatars / lip-sync) requires; building 2b as a realtime pipeline makes phase 3 "plug
the avatar into the stream" rather than a re-architecture.

**Guiding principle (unchanged from 2a):** build the streaming *mechanism* as a general
capability, but ship exactly one consumer — the **debug runner** with an audio toggle — so the
whole path is exercisable end-to-end. Non-streaming and text-only behavior stay unchanged.

## 2. Locked decisions (from brainstorming — each an explicit user choice)

1. **Realtime WS pipeline (not END-node HTTP chunking).** The chosen approach is
   agent-text-deltas → ElevenLabs WebSocket `stream-input` → audio chunks back, concurrently
   with generation. Rationale: it is the only option that (a) starts audio before the text is
   done, (b) yields native `normalizedAlignment` for lip-sync, and (c) produces a raw PCM
   stream avatar SDKs consume — i.e. maximally sets up phase 3. It is the heaviest of the
   candidates; that cost is accepted because the north-star is avatars.
2. **Voice lives on the AGENT node.** Audio must begin as tokens are born, so the TTS session
   is opened by the speaking agent, not the (post-agent) END node.
3. **Full move of output modality to the agent.** `output_type: text|voice` + the voice config
   move from END to the AGENT node; the phase-1 buffered base64 synthesis also moves from END
   to the agent (the non-streaming path). END keeps only source selection (`output_mode`),
   state/project filters, and session/error flags — it becomes the single, unambiguous *final
   output selector*, and the AGENT node the single source of truth for modality.
4. **Audio format = PCM 16 kHz** on the wire (avatar-native; phase 3 connects without
   transcoding). The debug player uses the Web Audio API (raw PCM cannot use `<audio>`).
5. **Single consumer = the debug runner** with an audio player, mirroring 2a. A production
   chat streaming UI is a later spec.

## 3. Scope

### In scope (2b)

- A new `capability:"realtime"` route in the voice catalog + an **ElevenLabs realtime WS
  client** (`stream-input`) in `external/voice/realtime.py`.
- `AgentNodeConfig.output_type: "text"|"voice"` and `AgentNodeConfig.voice: VoiceModelConfig`
  (provider / credential / model / voice_id), migrated off the END node.
- A **realtime TTS coordinator** (`RealtimeTTSSession`): the agent's text deltas are teed —
  emitted as `STREAM_DELTA` (text, unchanged 2a) **and** pushed into the WS — while a
  concurrent receive loop emits a new `AUDIO_DELTA` event (base64 PCM + optional alignment).
- A new `DebugEventType.AUDIO_DELTA` with `AudioDeltaEventData` (+ `AlignmentData`), carried on
  the same buffer/SSE as text, but under a **transient (live-only) retention class** so heavy
  PCM never starves the replayable text/control history.
- Migration of the phase-1 buffered base64 synthesis from END to the agent (non-streaming
  path), and removal of all synthesis from the END node.
- Debug-runner: reuse the 2a stream toggle; add a **Web Audio PCM player** that plays
  `AUDIO_DELTA` chunks gaplessly, demuxed by `node_id`.
- A **fake ElevenLabs WS** test seam that scripts audio chunks + alignment, mirroring
  `mock_llm.set_stream` from 2a.

### Out of scope (explicitly deferred)

- **Production, non-debug chat streaming UI** — the mechanism works for any run; only the debug
  runner is wired.
- **AI avatars / lip-sync** — phase 3. But `AUDIO_DELTA` carries `alignment` **now**, so phase 3
  is a consumer addition, not a transport change.
- **Persisting audio or alignment** — ephemeral, exactly like text deltas in 2a and audio in
  phase 1. No replayable audio history; a client that reconnects after buffer expiry gets the
  final text (no audio), consistent with 2a.
- **A second base64 fallback on streaming runs** — deliberately excluded; that would be a
  second synthesis call (see §5, no-double-call guarantee).
- **Streaming voice for `json_object` agent output** — buffered/parsed as today.
- **A second realtime TTS provider** — the route accepts one; v1 implements only ElevenLabs.

## 4. Architecture and data flow

### 4.1 The realtime pipeline (one streaming voice turn)

```
AGENT node — gated for LIVE audio (all of §4.4 hold)
  │
  ├─(1) resolve voice credential (get_voice_api_key_with_fallback — as phase-1 END did)
  ├─(2) open EL WS:  wss://…/text-to-speech/{voiceId}/stream-input
  │        ?model_id=…&output_format=pcm_16000  + BOS(voice_settings, chunk_length_schedule)
  │        └─► spawn recv-task ──► per audio chunk ──► emit_audio_delta(pcm, alignment, node_id)
  │
  └─(3) AgentRunner.run(on_delta = TEE):
             on_delta(text) ├─► emit STREAM_DELTA          (text — unchanged 2a transport)
                            └─► push text → WS send-queue  (drives realtime synthesis)
        ─── agent run returns ───
  (4) send EOS → recv-task drains final audio → close WS
  (5) emit step_complete  (voice cost from synthesized chars — phase-1 contract)

One seq'd stream, one SSE (GET /executions/{id}/stream):
  step_start · STREAM_DELTA · AUDIO_DELTA(+alignment) · step_complete · execution_complete
  → client demuxes by node_id/type; text replays by cursor, audio is live (§4.3)
```

**Two distinct connections — do not conflate:**

- **Internal:** backend ⇄ ElevenLabs WS (`stream-input`). Opened and closed *inside* the agent
  node's execution, from whichever process runs the node. Never exposed to the client.
- **External:** client ⇄ backend over the **same SSE as 2a**. The client speaks HTTP/SSE only,
  never a WebSocket. Audio arrives as `AUDIO_DELTA` (base64 PCM) alongside `STREAM_DELTA`.

The client subscribes exactly as in 2a — by `execution_id`:

- **Two-request (API, `task=true`):** `POST …/execute {task:true, stream:true, input}` →
  `202 {execution_id}` → `GET /executions/{execution_id}/stream` (SSE, `Last-Event-ID`). The
  `execution_id` from the 202 is the subscription key.
- **Inline single-request (what the debug runner uses in 2a):** `POST /execute/debug
  {stream:true}` — the HTTP response *is* the SSE stream; audio arrives on that same response.

**2b adds no client-facing endpoint** — only a new event type on the existing stream.

### 4.2 Ordering guarantee

All `AUDIO_DELTA` events for a node arrive **before** that node's `step_complete`, because the
agent node flushes (EOS) and drains the WS receive loop before emitting `step_complete`. There
is no separate `audio_end` event: a node's audio is complete at its `step_complete`.

### 4.3 Transport — heavy PCM must not starve the replay buffer

The 2a buffer retains *every* event (in-memory `deque(maxlen)` / Redis Stream `MAXLEN`). PCM
chunks are large and frequent — retaining them would evict `step_*`/text events and balloon
memory. Therefore the stream carries **two retention classes**:

- **Retained / replayable** (seq, cursor) — `step_start`, `STREAM_DELTA`, `step_complete`,
  `execution_complete`, `error`. Unchanged from 2a; text replay is unaffected.
- **Transient / live-only** — `AUDIO_DELTA` (with `alignment` inside). Fanned out to live
  subscribers, **not** retained in cursor-replay history (or only in a tiny rolling window).
  Replaying already-played audio on reconnect is pointless; the avatar/player resumes live.

A seq is still assigned to every event so the client can order audio relative to text, but the
replay history excludes audio. Backend mapping (see §4.5): the transient class is an in-memory
bounded ring or a Redis Pub/Sub channel — both live-only by nature.

### 4.4 Gating — the five-condition rule

`AUDIO_DELTA` (LIVE audio) is produced for an agent node **iff all hold**:

1. `request.stream is True` (the run streams), **and**
2. the agent node `stream is True` (2a eligibility — live audio tees off the text-delta path),
   **and**
3. `output_type == "voice"` and `voice` is fully configured (voice_id + model), **and**
4. the resolved model has a realtime route (`capability:"realtime"`), **and**
5. the resolved `response_format == "text"` (not `json_object`).

Three mutually exclusive outcomes:

- **1–5 hold** → LIVE WS (PCM stream), no base64.
- **`output_type == "voice"` but 1/2/4/5 fail** → BUFFERED base64 synthesis at the agent (the
  migrated phase-1 path).
- **`output_type == "text"`** → no voice; behavior unchanged.

`validate_config()` warns: voice with no voice selected; `voice + stream + json_object`
(streaming voice needs text) → warn + buffered; a realtime model with `stream=false` → warn it
will run buffered.

### 4.5 Redis-optional behavior (self-host default = no Redis)

The ElevenLabs WS is **independent of Redis** — it is an outbound connection from whichever
process runs the agent node. Redis only governs how audio crosses the worker→API process
boundary before the SSE subscriber.

| Aspect | No Redis (self-host default) | Redis (queued tier) |
| ------ | ---------------------------- | ------------------- |
| Agent runs in | API process (inline `asyncio.create_task`) | arq worker (separate process) |
| EL WS opened from | API process | worker process |
| SSE subscriber | same process as agent | different process (API) |
| Text/control transport | in-memory deque (cursor replay) | Redis Stream `stream:events:{id}` (as 2a) |
| **Audio (`AUDIO_DELTA`)** | in-memory bounded ring, same-process fan-out | **separate** `stream:audio:{id}` channel (Pub/Sub / small-MAXLEN Stream), cross-process |
| Reconnect | text from cursor, audio live | text from cursor, audio live |

The transient audio class maps cleanly onto both backends: an in-memory ring ⟷ Redis Pub/Sub
(live-only by nature). **2b introduces no new Redis requirement for self-host** — inline mode
works fully; Redis is needed only for the cross-process worker tier, as today. The existing
`DEBUG_EVENTS_USE_REDIS` toggle selects the backend for the audio channel too (no second
switch).

## 5. The no-double-synthesis guarantee

After the full move (§2.3), **the END node contains no synthesis code** — nothing can call it a
second time. Synthesis exists only in the agent path, where exactly one branch runs per
execution:

- **Streaming run:** the agent streams live PCM; **no base64 is produced**; END returns text
  only; audio is ephemeral (as text deltas in 2a).
- **Non-streaming run:** the agent synthesizes **once** (buffered base64 in its node output);
  `output_mode == "last_agent"` at END merely passes that output through — END does **not**
  synthesize.

The guarantee holds structurally (one module, one active branch), not by discipline.

## 6. Components and interfaces (unit boundaries)

| Unit | Responsibility | Depends on |
| ---- | -------------- | ---------- |
| `external/voice/realtime.py` (`RealtimeTTSSession`) | EL WS `stream-input`: BOS/send/recv/EOS, alignment, flush/close; two asyncio tasks (send-pump, recv-loop) | WS lib (spike), voice catalog |
| `external/voice/voice_catalog.py` + `models/elevenlabs.json` | register realtime models (`capability:"realtime"`) | — |
| `AgentNodeConfig.output_type` / `voice` + `validate_config` (`schemas/node.py`) | modality config on the agent + warnings | — |
| agent-node gating (`nodes/agent_node.py`) | the five-condition rule → live / buffered / text; resolve credential; own the coordinator | credential service, `RealtimeTTSSession`, synthesis |
| `AudioDeltaEventData` + `AlignmentData` (`schemas/debug_events.py`) | new event type + alignment | — |
| stream buffer (transient audio class) + `emit_audio_delta` (`debug_event_manager.py`, `stream_buffer.py`) | live-only fan-out, not in replay; bounded ring | buffer, Redis (optional) |
| Redis audio channel `stream:audio:{id}` | cross-process audio in queued mode | Redis (optional) |
| END node simplification (`nodes/end_node.py`) | remove all synthesis; keep source selection / filters / flags | — |
| debug player (frontend) | Web Audio PCM (gapless), demux by node_id, stream toggle | SSE endpoint |
| fake EL WS (`tests/`) | scripted audio chunks + alignment for tests | — |

## 7. Error handling — audio is best-effort, text is source of truth

| Situation | Behavior |
| --------- | -------- |
| WS open fails (bad key / network) | log; no audio; agent streams text; run **succeeds** text-only (mirrors phase-1 fallback) |
| WS fails mid-stream | stop audio; text keeps streaming; delivered PCM stays (as partial text in 2a); run does not fail |
| Agent errors mid-stream | close/abort WS; normal `error` event → `FAILED` (as 2a) |
| Char ceiling exceeded | early EOS to WS; text keeps streaming; metering counts only synthesized chars |
| Timeout | `total_timeout` bounds the run; WS closed |

Consistent with phase 1 (text-only fallback) and 2a (partial deltas stay): **audio never fails
the run.**

## 8. Metering — unchanged contract

Cost is per **actually-synthesized** character (chars fed to the WS before EOS/ceiling),
computed once at the agent's `step_complete`, emitted as the existing facts
`{cost, cost_kind:"voice", used_system_key, chars, voice_provider, voice_model}` → cost
accumulator → deduction, under the same `VOICE_USAGE` ledger, behind `billing_enabled`. Own-key
free; system-key metered ×margin, exactly as phase 1. Exact ElevenLabs billed-character
semantics for the WS route are confirmed in the spike (§11).

## 9. Configuration (new settings, with starting defaults)

- `STREAM_AUDIO_BUFFER_MAX_CHUNKS` (default ~`50`) — transient audio ring size / audio-Stream
  `MAXLEN`.
- `ELEVENLABS_WS_BASE_URL` — WS base override for a proxy (parallels `elevenlabs_api_base_url`).
- `voice_realtime_output_format` (default `"pcm_16000"`) and a default `chunk_length_schedule`.
- Reuses existing `voice_output_max_chars` (ceiling), `DEBUG_EVENTS_USE_REDIS` (backend),
  `STREAM_BUFFER_TTL_SECONDS`.

(Starting defaults unblock implementation; §11 flags tuning once real audio volumes are seen.)

## 10. Testing strategy

Per backend rule **§0**, the concrete test cases come from the user at the start of the plan.
The harness this spec adds: a **fake ElevenLabs WS** that scripts audio chunks + alignment in
response to fed text (no network), mirroring `mock_llm.set_stream` from 2a.

Unit coverage themes (final cases from the user):

- Gate matrix — each of the five conditions off → buffered or text as specified.
- `AUDIO_DELTA` ordering: all audio for a node precedes its `step_complete`.
- Retention classes: audio is transient (absent from cursor replay); text/control replay
  unchanged.
- Backend parity: no-Redis in-memory ring ↔ Redis audio channel deliver equivalently.
- WS-open-fail → text-only success; WS-mid-fail → partial audio + run OK; agent-error →
  `FAILED` + WS closed.
- Metering counts synthesized chars; own-key vs system-key; `billing_enabled=false` inert.
- END has no synthesis path (double-call structurally impossible).
- Non-streaming voice = one buffered base64 at the agent, passed through by END.

Verify e2e via `curl` against the SSE endpoint, plus a browser dogfood of the Web Audio player.

## 11. Open items to confirm during planning

- **Spike #1 (first task):** live ElevenLabs `stream-input` WS with a real key — exact protocol
  (BOS/text/EOS), chunk format at `output_format=pcm_16000`, `normalizedAlignment` shape,
  `chunk_length_schedule`/`try_trigger_generation` behavior, socket-close semantics, billed-char
  accounting, and the WS library choice (`websockets` via `uv add` vs the ElevenLabs SDK). Plus
  a Web Audio gapless-PCM playback spike. Adjusts §4.1 / §7 / §8 wording.
- Exact transient-audio retention: pure live-only vs a small rolling window; final
  `STREAM_AUDIO_BUFFER_MAX_CHUNKS`.
- The realtime ElevenLabs model list to seed with `capability:"realtime"`, and whether a model
  can serve both the `speech` (buffered) and `realtime` routes.
- Char-ceiling behavior on the streaming path (guard-and-stop vs no cap) and how it interacts
  with metering.
- Migration of any existing END-voice workflow config to the agent node (schema/DTO + frontend
  form move + possible data migration of saved graphs); low burden if phase 1 is unmerged.
- Whether multiple voiced agents in one graph are allowed (each synthesizes) or constrained to
  one.

## 12. Spike results (2026-07-07, live `stream-input`)

Confirmed against a real key + account voice, model `eleven_flash_v2_5`, `output_format=pcm_16000`:

- **WS URL:** `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id=…&output_format=pcm_16000`. Auth via `xi_api_key` inside the BOS JSON. `try_trigger_generation: true` accepted.
- **Receive message keys:** `audio` (base64 PCM), `normalizedAlignment`, `alignment`, `isFinal`.
- **Alignment is camelCase:** `chars: list[str]`, `charStartTimesMs: list[int]`, `charDurationsMs: list[int]`. `RealtimeTTSSession._parse_alignment` reads both camelCase and snake_case, so no change needed. We use `normalizedAlignment` (normalized to spoken text).
- **Framing:** audio arrives in a few chunks (~14–17 KB PCM each ≈ 0.45 s @16 kHz); the terminal message has empty `audio` and `isFinal: true`. The recv loop stops on `isFinal` or socket close.
- **PCM format:** signed 16-bit LE mono @16 kHz — matches the Web Audio player plan (Int16 → Float32 `/32768`).
- **Decisions confirmed:** live path is NOT char-capped (only the buffered path caps via `voice_output_max_chars`); multiple voiced agents allowed (each owns its session). WS library = `websockets` (already in the dependency tree).
