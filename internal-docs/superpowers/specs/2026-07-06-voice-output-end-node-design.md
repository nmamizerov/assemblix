# Voice output on the END node (ElevenLabs, non-streaming) — Design

- **Date:** 2026-07-06
- **Status:** Approved design (pre-implementation)
- **Sub-project:** 1 of 3 in the "conversational voice + avatars" initiative
- **Author:** design session (brainstorming)

## 1. Context and the larger initiative

Assemblix is a visual workflow/agent platform. Users build graphs of nodes (START,
AGENT, CONDITION, SET_VARIABLE, HTTP_REQUEST, STICKER, END) and run them; a chat turn
is a workflow execution and the final reply is produced at the END node.

The goal of the larger initiative is a genuinely strong conversational product that can
answer in multiple modalities. It decomposes into **three sequential sub-projects**, each
building on the previous one:

| # | Sub-project | Depends on |
|---|-------------|------------|
| **1** | **Voice output on the END node (ElevenLabs, non-streaming)** — *this spec* | the existing `external/voice/` seam |
| 2 | Streaming (token-level LLM streaming + audio-chunk transport) | #1 |
| 3 | AI avatars (anam.ai / liveavatar, real-time lip-sync) | #2 |

**Guiding principle for #1:** extend the voice seam the codebase already reserved, do not
touch the execution core, and make everything we build here (node config, credential
model, voice picker, chat player, metering) survive the later addition of streaming
without rework.

### Why this sub-project is smaller than it looks

The recent voice **input** feature (server-side STT) shipped a data-driven voice module
`external/voice/` that mirrors `external/llm/`. Critically, its catalog schema already
reserves `capability: "speech"` (TTS) and `"realtime"`, and `VoiceModelMetadata` already
carries a cost field. So voice output is "finish the reserved seam", not "build from
scratch".

## 2. Scope

### In scope (v1)

- A **text | voice** output mode on the END node; under voice: provider → credential →
  live voice picker → model.
- **ElevenLabs** as the first (and only) TTS provider in v1, via a direct ElevenLabs
  client (not LiteLLM — we need `GET /voices`).
- **Live voice list** fetched from the user's ElevenLabs account using their stored token.
- **BYO credential and platform (system) token**, gated by plan exactly like LLM keys.
- **Per-character credit metering** of system-token usage, reusing the existing
  `metadata{cost, used_system_key}` → accumulator → post-execution deduction contract.
- **base64-inline audio delivery** in the live execution response / debug SSE; audio bytes
  are **not** persisted to the database.
- A **configurable character limit** on synthesized text (per-node field + platform
  ceiling), with **text-only fallback** when exceeded.

### Out of scope (explicitly deferred)

- **Streaming** of tokens or audio — sub-project #2. Once streaming lands, delivery
  becomes chunked and the base64-blob concern disappears; therefore we deliberately do
  **not** build object storage / S3 for v1.
- **Persisting audio in chat history / replay from history** — audio lives only in the
  live response for v1 (mirrors how STT audio is not persisted server-side today).
- **A second TTS provider** — the architecture accepts one (OpenAI TTS is nearly free to
  add later via the existing LiteLLM seam), but v1 implements only ElevenLabs.
- **Metering STT (voice input)** — the STT path has an unused `cost_per_minute` field and
  is currently not metered; we leave it untouched. Can be a small follow-up on the same
  pattern.
- **AI avatars** — sub-project #3.

## 3. Decisions log (with rationale)

1. **Non-streaming first.** Nothing streams today (the AGENT node returns the full
   completion; the production path is synchronous-with-polling). Streaming is a
   cross-cutting core change; shipping non-streaming unblocks the whole voice mechanism
   without touching the engine.
2. **Live voice list from the account.** Best UX and lets users use their own/cloned
   voices. Requires a direct ElevenLabs client and a "voices by credential" endpoint.
3. **base64-inline delivery; audio not persisted.** The repo has **no** object storage of
   any kind (KB extracts PDF→text and discards bytes; STT transcribes-and-discards). base64
   inline is the zero-infra path that matches the architecture. To protect the DB, audio
   bytes are scrubbed before the execution row is persisted — the DB keeps text + a small
   marker.
4. **Full system-token + metering in v1.** Mirrors the existing LLM system-key pattern.
   Own-key usage is free (user pays the provider directly); system-token usage is metered
   in credits (× margin), exactly like LLM system keys.
5. **Separate `VOICE_USAGE` ledger type.** Since metering was explicitly requested, itemize
   TTS spend separately rather than folding it into the combined `LLM_USAGE` row.
6. **Character limit, per-node + platform ceiling, text-only fallback on exceed.** A single
   char cap bounds payload size, DB growth, and cost simultaneously. Characters (not words)
   because ElevenLabs bills per character and audio size correlates with characters; the UI
   may show a word-count hint. On exceed: skip synthesis, return full text, no audio (safe,
   no truncation surprises, no surprise spend).
7. **Synthesis runs inside `EndNode.execute()`.** The END node already assembles the final
   text; doing synthesis there makes END a normal node that emits per-step billing facts —
   which is precisely what the metering contract expects. (STT is a pre-engine gate because
   text must exist before the run; TTS is post-text, i.e. at the final node — symmetric.)

## 4. Architecture

### 4.1 Data flow (one voice chat turn)

```
AGENT produces text ──► END node (outputFormat = "voice"):
  1. take the final text (last_agent / specific_agent / custom — unchanged)
  2. if len(text) > effective char limit:  →  text-only fallback (skip 3–5)
  3. resolve_voice_credential("elevenlabs", credential_id, plan)
        → (api_key, is_system_key)          # same can_use_own_keys gating as LLM
  4. ElevenLabs POST /v1/text-to-speech/{voiceId} → mp3 bytes
  5. NodeOutput.data     = { message, audio: { base64, format:"mp3", voiceId, model } }
     NodeOutput.metadata = { cost: chars * cost_per_char_usd,   # only when is_system_key
                             used_system_key, chars, voice_provider, voice_model }
                                   │
   cost_accumulator ──► context.(system|own)_key_cost_usd   # existing, provider-agnostic
                                   │
   _finalization_phase ──► CreditService.deduct_for_execution  # existing, unchanged
                                   │
   persistence ──► execution row stores text + marker (audio base64 scrubbed)
   live response / debug SSE ──► carries audio base64 to the client
```

The billing module, the cost accumulator, and the executor need **no changes** — the END
node simply emits the same `{cost, used_system_key}` facts the AGENT node already emits.

### 4.2 Backend components

**Credentials & providers**
- `enums.py`: add `CredentialsType.ELEVENLABS_TOKEN`. Alembic migration
  `ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'ELEVENLABS_TOKEN'` (follow the
  existing deepseek/gigachat migration pattern; note the enum stores UPPERCASE member
  names).
- `core/settings.py`: add `system_elevenlabs_api_key: str | None` and
  `voice_output_max_chars: int` (platform ceiling, sensible default).
- **Voice-aware credential resolution.** A new resolution path (parallel to
  `CredentialsService.get_api_key_with_fallback`, not a modification of it) that maps a
  voice provider → credential type (`elevenlabs → ELEVENLABS_TOKEN`), applies the same
  `can_use_own_keys` plan gate, resolves the system ElevenLabs key when appropriate, and
  returns `(api_key, is_system_key)`. The LLM path (`AgentProvider`-keyed maps) stays
  untouched — ElevenLabs is intentionally **not** shoehorned into `AgentProvider`.

**Voice catalog & pricing**
- `external/voice/models/elevenlabs.json`: speech models (e.g. `eleven_multilingual_v2`,
  `eleven_turbo_v2_5`, `eleven_flash_v2_5`) with `capability: "speech"` and a per-character
  price field (`cost_per_char`).
- `external/voice/base.py`: add `cost_per_char` to `VoiceModelMetadata`.
- `external/voice/voice_catalog.py`: add `VOICE_PROVIDER_LABELS["elevenlabs"] = "ElevenLabs"`.
- `external/voice/pricing.py` (or a `compute_tts_cost` helper next to
  `external/llm/pricing.py`): `chars * cost_per_char`.

**ElevenLabs client & synthesis**
- `external/voice/elevenlabs.py`: `list_voices(api_key)` (`GET /v1/voices`) and
  `synthesize(api_key, voice_id, model, text)` (`POST /v1/text-to-speech/{voice_id}` →
  mp3 bytes).
- `external/voice/synthesis.py`: a `synthesize()` seam sibling to `transcription.py` that
  routes to the ElevenLabs client (and later other providers), returning audio bytes +
  metadata (chars, model).

**REST**
- `api/rest/voice.py`: make `/voice/providers` capability-parameterized (it currently
  hardcodes `transcription`) so the END form can request `?capability=speech`.
- New endpoint `GET /voice/credentials/{credential_id}/voices`: authorize the credential,
  decrypt the token, call `list_voices`, return `[{id, name, previewUrl?}]`. This powers
  the live voice dropdown.

**Node**
- `schemas/node.py`: extend `VoiceModelConfig` with an optional `voice_id`; extend
  `EndNodeConfig` with `output_format: Literal["text","voice"] = "text"`,
  `voice: VoiceModelConfig | None`, and `voice_max_chars: int | None`.
- `nodes/end_node.py`: when `output_format == "voice"`, after assembling the final text,
  enforce the effective char limit (`min(node.voice_max_chars or ∞, settings ceiling)`),
  either synthesize (via `external/voice/synthesis.synthesize`, using the resolved
  credential) or fall back to text-only, and populate `NodeOutput.data.audio` +
  `NodeOutput.metadata` with the billing facts. `credential_service` is available on
  `ExecutionContext`.

**Billing (EE, minimal)**
- `database/models/credit_transaction.py`: add `CreditTransactionType.VOICE_USAGE`.
- `credit_service.deduct_for_execution`: itemize voice cost under `VOICE_USAGE` (either a
  separate ledger row or a `meta` breakdown). Keep all of this behind `billing_enabled`
  and in the EE-licensed module — the voice-synthesis code stays billing-free.

### 4.3 Frontend components

- `entities/credential/model/types.ts` + `config.ts`: add the ElevenLabs credential type
  (label + icon). The generic `{type, name, value}` create form needs no change.
- `entities/voice-model/`: add a hook to fetch speech providers/models
  (`?capability=speech`) and a hook to fetch voices by credential
  (`GET /voice/credentials/{id}/voices`).
- `entities/workflow/model/types.ts`: mirror the `EndNodeConfig` / `VoiceModelConfig`
  extensions (camelCase: `outputFormat`, `voice`, `voiceId`, `voiceMaxChars`).
- `end-node-form.tsx`: add a text/voice toggle; under voice, reuse the START-node voice
  picker pattern (`start-node-form.tsx`) — provider → credential → **live voice dropdown**
  → model — plus the char-limit field.
- Chat rendering (`use-workflow-debug.ts` and the message component): when a reply carries
  `audio.base64`, decode → blob URL → `<audio>` player, mirroring how recorded input clips
  already become blob URLs.

## 5. Licensing / EE boundary

- Voice synthesis, the ElevenLabs client, the catalog, the node, and the resolution helper
  are **core (OSS)** and billing-free.
- All monetary logic (system-key minting gate, credit deduction, the `VOICE_USAGE` ledger
  entry) stays behind `billing_enabled` and inside the EE-licensed `billing/` module,
  consistent with the rule that billing must not be entangled into core execution paths.
- Self-host default (`BILLING_ENABLED=false`, default BUSINESS plan, own keys): the voice
  feature works with a user's ElevenLabs credential and no charge is applied.

## 6. Testing approach

Per the backend rules, **new-feature test cases come from the user** — they must be
described before tests/implementation. Anticipated areas to cover (to be confirmed with
concrete cases at planning time):

- Voice-aware credential resolution: own-key vs system-key vs plan-forced-system, and the
  ElevenLabs-token-type compatibility check.
- Char-limit enforcement: under limit → synthesized; over limit → text-only fallback
  (no audio, no cost emitted); node-limit vs settings-ceiling precedence.
- Metering: system-key run emits `cost` and produces a `VOICE_USAGE` deduction; own-key
  run emits no charge; `billing_enabled=false` is inert.
- END node output shape for `text` (unchanged, backward-compatible) vs `voice`.
- Audio is present in the live response but scrubbed from the persisted execution row.
- ElevenLabs client calls are mocked at the external seam (no live API in unit tests).

## 7. Open items to confirm at planning time

- Concrete default values: `voice_output_max_chars` ceiling and the ElevenLabs
  `cost_per_char` per model (verify current ElevenLabs pricing at implementation).
- Exact ElevenLabs model list to seed in the catalog JSON.
- Whether the voice list endpoint caches results briefly (ElevenLabs `GET /voices` per
  keystroke would be wasteful — likely fetch once on credential selection).
- The precise scrub-before-persist seam for audio (where the execution output is trimmed
  before it is written to `execution_steps`), confirmed against `node_runner`/executor
  persistence.
