# AI Avatars — Design Spec (Phase 3)

**Date:** 2026-07-08
**Status:** Approved (design), pending implementation plan
**Depends on:** Phase 2a (text-token streaming) and 2b (streaming voice) — both implemented on
`feat/streaming-voice-output`. This phase reuses the **text** streaming pipeline (2a), not the
audio/PCM pipeline (2b).
**Branch (proposed):** `feat/ai-avatars`

---

## 1. Goal

Add **AI avatars** as a third agent-output modality, so a workflow can drive a real-time,
lip-synced talking avatar (anam.ai first) in a conversational session. Two non-negotiable
constraints, carried from the voice work:

1. **Reuse the existing approach as much as possible** — provider catalog, credentials
   with system/BYO fallback, discovery API, streaming SSE, voice input/STT.
2. **Aim for multi-provider from day one** — anam now; liveavatar / others later, behind a
   stable abstraction (like the voice provider seam).

A third, decisive constraint emerged during brainstorming:

3. **API-first.** The primary deliverable is a **provider-independent HTTP API** that lets
   *any* frontend embed an avatar conversation. Our own conversational screen is just the
   first reference consumer of that API. (An npm embed package is explicitly out of scope
   for this phase.)

---

## 2. How anam actually works (grounding facts)

Researched from anam.ai docs. These facts shape the architecture:

- **Session token minted server-side:** `POST /v1/auth/session-token` with a `personaConfig`
  (`name`, `avatarId`, `avatarModel`, `voiceId`, `llmId`) returns a short-lived token. The
  provider API key never reaches the browser — identical trust model to our voice system/BYO
  keys.
- **`llmId: "CUSTOMER_CLIENT_V1"` disables anam's own "brain"** — the avatar only speaks text
  we push; it does not think for itself.
- **Speech is driven by the client SDK, not the server.** There is **no** server-side "talk"
  API. The WebRTC session and rendering live in the browser. To speak:
  `createTalkMessageStream()` → `streamMessageChunk(text, isFinal)` → `endMessage()` (or the
  one-shot `talk(text)`). Video renders via `streamToVideoElement(...)`.
- **Provider STT is inconsistent across the market and coupled to the provider "brain":**
  anam has built-in STT (`MESSAGE_HISTORY_UPDATED`) but it belongs to the brain we disable;
  HeyGen/LiveAvatar docs state custom input requires **your own** STT; Tavus bundles STT in
  its own pipeline; Simli has **no** STT (pure lip-sync layer). Therefore provider STT is not
  a safe basis for a portable multi-provider design.

### Consequence: corrected mental model

The initial idea ("backend streams text chunks directly into the running anam session") is
**not possible** — anam has no server-side talk API. Text must pass through the client SDK.
But this barely dents the "frontend does nothing extra" goal: the frontend **already**
receives agent text deltas over SSE (phase 2a `STREAM_DELTA`). The only new client work is a
thin forwarder — for each avatar-tagged delta, call `talkStream.streamMessageChunk(delta)`.

---

## 3. Locked decisions (from brainstorming)

Each was an explicit user choice:

- **Arch A — client orchestrates** (not anam-orchestrated custom-LLM webhook). The client
  mints a token, renders the avatar, sends the user's turn to Assemblix, runs the workflow
  with `stream=true`, and forwards the avatar node's deltas into the provider SDK. Rationale:
  the anam-orchestrated webhook (Arch B) needs a publicly reachable OpenAI-compatible endpoint
  (bad for self-host), couples us to the OpenAI request shape, hands STT/turn-taking to the
  provider, and has a per-provider webhook contract (weaker multi-provider). Arch A keeps STT
  and turn-taking authority with us and is portable across providers (every avatar SDK has a
  "speak this text" client method).
- **Our STT is canonical** (reuse the START-node `voice_gate`/transcription path). The client
  sends the user's turn as **audio or text**; audio is transcribed by us. Provider STT is at
  most an optional client-side shortcut for an embedder — never part of our API contract.
- **Avatar config is workflow-global**, set in the editor header — not per agent node. This
  differs from `voice`, where the picker config lives on the node.
- **Avatar output is a per-node opt-in:** the agent node's `output_type` gains `"avatar"`.
- **API-first**, our route is the reference consumer. **No npm embed package** this phase.
- **anam only** this phase; the abstraction supports adding providers without contract change.

---

## 4. Architecture

### 4.1 The three API contracts (provider-independent)

1. **Mint a session** — `POST /api/workflows/{id}/avatar/session`
   - Backend resolves the avatar API key (system vs BYO, same fallback rules as voice), reads
     `workflow.config["avatar"]`, and calls the provider's session API (anam
     `POST /v1/auth/session-token`) with the persona built from that config.
   - Returns `{ provider, sessionToken, videoConfig }` — exactly what the client needs to
     `createClient(...)`. The provider key never leaves the backend.

2. **A user turn** — reuse the existing streaming run endpoint (`…/execute…`, `stream=true`).
   - The turn is submitted as **audio or text**. Audio → `voice_gate.transcribe_into_input_data`
     → workflow run (no new transport).
   - Response is the existing SSE stream of `STREAM_DELTA` events, each tagged with `node_id`.
     Deltas originating from an `output_type == "avatar"` node additionally carry an
     `avatar: true` flag so the client knows which deltas to forward.

3. **Discovery** — `/api/avatar/*`, a mirror of `/api/voice/*`:
   - `GET /providers`, `GET /providers/{p}/models`,
     `GET /credentials/{id}/avatars`, `GET /providers/{p}/system-avatars`.

### 4.2 Backend components (mirror `external/voice/`, lighter — no realtime WS, no PCM, no synth)

```
external/avatar/
  base.py            # AvatarModelMetadata (id, label, avatar_model, capability, cost_per_min)
  avatar_catalog.py  # AVATAR_PROVIDER_LABELS = {"anam": "Anam"}; find/list/list_providers
  models/anam.json   # avatars/personas as data
  anam.py            # adapter: mint_session_token(api_key, persona_cfg), list_avatars, list_voices
  session.py         # dispatch: mint_session(provider, ...) → if provider == "anam": ...
```

- **Credentials:** new `CredentialsType.ANAM_TOKEN`;
  `_AVATAR_PROVIDER_TO_CREDENTIALS_TYPE = {"anam": CredentialsType.ANAM_TOKEN}`;
  `get_avatar_api_key_with_fallback(...)` in `credentials_service.py`, cloned from
  `get_voice_api_key_with_fallback` (FREE → system key; paid → valid BYO else fall back).
- **Settings:** `system_anam_api_key` (`SYSTEM_ANAM_API_KEY`), `anam_api_base_url`
  (`ANAM_API_BASE_URL`). Feature gate = key presence + `AVATAR_PROVIDER_LABELS` (no separate
  boolean flag, matching voice).
- **Discovery router:** `api/rest/avatar.py` (`/api/avatar`), a copy of `api/rest/voice.py`.
- **Session router:** `POST /api/workflows/{id}/avatar/session` → resolve key →
  `mint_session(...)` → `{ provider, sessionToken, videoConfig }`.
- **Migration:** one migration for the new `CredentialsType` enum value only. `config.avatar`
  and the node `output_type` value are JSON — no schema migration.

### 4.3 Multi-provider is **two-sided** (new vs voice)

Voice providers lived only on the backend. Avatars render client-side, so the abstraction has
two halves:

- **Backend side** (§4.2): a token-minting adapter per provider (each provider's session API
  differs). `if provider == "..."` dispatch in `session.py`, mirroring `synthesis.py` — a
  deliberate match to the existing (non-polymorphic) voice seam, not an over-engineered ABC.
- **Client side** (new): a narrow render adapter interface — this one **is** a real interface,
  because otherwise each provider's SDK bleeds into UI code:

  ```ts
  interface AvatarRenderer {
    connect(sessionToken, videoEl): Promise<void>
    speak(): { chunk(text): void; end(): void }   // createTalkMessageStream/streamMessageChunk
    disconnect(): void
  }
  ```

  `AnamRenderer` is the first implementation. The client selects the adapter by the `provider`
  field returned from the mint call. Adding liveavatar later = one backend adapter + one client
  adapter; the three API contracts do not change.

### 4.4 Config & node changes

- **Workflow-global avatar config:** `workflow.config["avatar"]`
  (`{ provider, avatarModel, avatarId, voiceId?, credentialId? }`), edited in the editor
  header. New `WorkflowAvatarConfig` DTO.
- **Agent node:** `output_type` extends to `Literal["text", "voice", "avatar"]`. `"avatar"`
  means "stream text (reuse 2a `stream=true`) and mark its deltas `avatar: true`." There is
  **no** per-node avatar config — persona/voice are workflow-global.
- **Validation warning:** a node with `output_type == "avatar"` while `workflow.config.avatar`
  is empty → yellow canvas warning (like `voiceStreamHint`); soft validation on the backend,
  not a hard fail.

### 4.5 Frontend

- **Discovery picker:** `AvatarOutputPicker`, cloned from the already provider-generic
  `VoiceOutputPicker` (provider → credential → avatar/voice cascade), placed in the workflow
  editor header. Backed by a new `avatar-model` RTK entity mirroring `voice-model`
  (`/api/avatar/*`, `AvatarModels` cache tag).
- **Agent node form:** third `output_type` option ("AI avatar"); yellow warning when the
  workflow has no avatar configured. New credential mappings in
  `provider-credential-type.ts` for the anam credential type.
- **Renderer:** `AvatarRenderer` interface + `AnamRenderer` (loads the anam JS SDK,
  `createClient` → `streamToVideoElement`, `createTalkMessageStream`).
- **Conversational screen (reference consumer):** a mode of the existing chat/run surface that,
  when the workflow has an avatar configured, mints a session, renders the avatar, captures the
  mic, submits turns as audio to `…/execute` (`stream=true`), and forwards `avatar: true`
  deltas into the renderer.
- **i18n:** ru/es/en keys for the picker, node option, warning, and conversational screen.

---

## 5. Data flow (end to end)

```
1. Client → POST /api/workflows/{id}/avatar/session
   backend: resolve key (system/BYO) → anam POST /v1/auth/session-token(personaConfig from config.avatar)
   ← { provider: "anam", sessionToken, videoConfig }
2. Client: AnamRenderer.connect(sessionToken, <video>) → WebRTC; avatar on screen (idle)
3. User speaks → client captures mic → POST …/execute (audio, stream=true)
   backend: voice_gate.transcribe → workflow run
4. Avatar agent node generates → STREAM_DELTA { node_id, avatar: true, text } over SSE
5. Client: per avatar delta → talkStream.streamMessageChunk(delta)
   node end → talkStream.endMessage() → anam speaks + lip-syncs with its own voiceId
6. User speaks again / interrupts → back to step 3
```

No new backend transport: the existing `execute + SSE STREAM_DELTA` (2a) is reused wholesale.
The `AUDIO_DELTA`/PCM path (2b) does not participate in the avatar flow.

---

## 6. Scope

### In scope (Phase 3)

- Backend: `external/avatar/` (anam), `CredentialsType.ANAM_TOKEN` +
  `get_avatar_api_key_with_fallback`, discovery `/api/avatar/*`, session-mint route, settings.
- Schema: `config.avatar` + `output_type == "avatar"` + soft validation warning.
- Frontend: `avatar-model` RTK entity, `AvatarOutputPicker` in the editor header,
  third `output_type` option in the agent node form, `AvatarRenderer`/`AnamRenderer`,
  conversational reference screen, ru/es/en i18n.
- One migration for the new `CredentialsType` enum value.

### Out of scope (deliberate)

- Separate npm embed package (`@assemblix/avatar-embed`) — later.
- A second provider (liveavatar, …) — the abstraction is ready; implement on demand.
- Provider STT — ours only.
- Persisting video/sessions, call recording.

### Open product questions (resolve in the plan)

- **Billing of avatar minutes:** reuse the existing voice cost accumulator, or introduce a
  dedicated `CreditTransactionType.AVATAR_USAGE`? (Avatars are billed per streamed minute by
  anam, unlike voice's per-character.)
- **Per-turn length ceiling** on the live avatar path (currently the streaming text path is
  uncapped).

---

## 7. Reuse map (what we clone vs build)

| Concern | Voice (existing) | Avatar (this phase) |
|---|---|---|
| Provider catalog | `external/voice/voice_catalog.py` | `external/avatar/avatar_catalog.py` (clone) |
| Provider adapter | `external/voice/elevenlabs.py` | `external/avatar/anam.py` (new: token mint) |
| Dispatch seam | `synthesis.py` (`if provider==`) | `session.py` (`if provider==`) |
| Credentials + fallback | `get_voice_api_key_with_fallback` | `get_avatar_api_key_with_fallback` (clone) |
| Discovery API | `api/rest/voice.py` | `api/rest/avatar.py` (clone) |
| Streaming transport | `STREAM_DELTA` SSE (2a) | **reused as-is** (+ `avatar` flag) |
| User STT | `voice_gate` (START node) | **reused as-is** |
| Node opt-in | `output_type: "voice"` + node `voice` cfg | `output_type: "avatar"`, config workflow-global |
| Config picker (FE) | `VoiceOutputPicker` | `AvatarOutputPicker` (clone) |
| RTK entity (FE) | `voice-model` | `avatar-model` (clone) |
| Rendering | backend synth → Web Audio player | **client-side** `AvatarRenderer`/`AnamRenderer` (new) |
| Session token mint | — (n/a for voice) | `POST /api/workflows/{id}/avatar/session` (new) |
```
