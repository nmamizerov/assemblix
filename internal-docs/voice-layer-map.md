# Map of `external/voice/`

This folder is not one feature. It is **four independent voice capabilities**, each
built the same way: a *seam* that hides the provider, plus one implementation per
provider. Everything else is a shared registry or a direct provider client.

Read this before adding anything here — two of the four have confusingly similar
names and are routinely mixed up.

## The four capabilities

| Capability | Direction | Seam (call this) | Implementations | Used by |
|---|---|---|---|---|
| `transcription` | audio → text | `transcription.py::transcribe()` | LiteLLM, `yandex.py` | `transcribe` node |
| `speech` | text → audio (one blob) | `synthesis.py::synthesize()` | `elevenlabs.py`, `yandex.py` | agent node, buffered voice output |
| `realtime` | text → audio (streamed) | `realtime_dispatch.py::create_realtime_session()` | `realtime.py` (ElevenLabs WS), `yandex_realtime.py` (gRPC) | agent node with live voice, avatars |
| `conversation` | audio ↔ audio (duplex) | `bridge_dispatch.py::create_bridge()` | `openai_bridge.py` | **Voice Agents** |

### The name trap

`realtime` and `conversation` sound like the same thing. They are opposites:

```
realtime      text  ──────────►  audio          the agent writes, we speak it
conversation  audio ◄─────────►  audio          the caller speaks, the model answers
```

`realtime` belongs to **voice inside workflows**. `conversation` belongs to **Voice
Agents**. They share nothing but the folder.

## How a capability is wired

Every capability follows the same three layers. Using `conversation` as the example:

```
       caller (runtime / node)
                │
                │  knows only the seam
                ▼
   bridge_dispatch.py            create_bridge(provider=...) → RealtimeBridge
                │                 raises NotImplementedError for unknown providers
                │
                ▼
   bridge.py                     the contract: RealtimeBridge protocol
                │                 + BridgeEvent, the normalized event vocabulary
                │
                ▼
   openai_bridge.py              the only file that imports the `openai` SDK
```

The rule this encodes: **provider vocabulary stops at the seam.** Above
`bridge_dispatch`, nothing knows whether it is talking to OpenAI or anyone else. The
same shape holds for `realtime_dispatch.py` → the two session classes, and for
`synthesis.py` / `transcription.py` → their providers.

## The registry

```
   voice_catalog.py  ──reads──►  models/openai.json
                                 models/gemini.json
                                 models/elevenlabs.json
                                 models/yandex.json
```

`voice_catalog.py` answers "which providers and models exist, for which capability,
at what price". The JSON files are the data; `base.py` is the type they are validated
against (`VoiceModelMetadata`: id, label, capability, route, cost).

**Adding a model is a JSON edit.** Adding a provider is a JSON file plus an entry in
`VOICE_PROVIDER_LABELS`, plus a branch in the relevant dispatcher if it needs one.

The catalog is what the frontend's provider/model pickers read, through
`/api/voice/providers?capability=…`.

## Everything else

| File | What it is |
|---|---|
| `conversation_voices.py` | Static voice (timbre) lists for OpenAI and Gemini. Static because neither exposes a voice-listing endpoint — same reason `yandex.py` hardcodes its own. |
| `elevenlabs.py`, `yandex.py` | Direct clients for providers that are **not** OpenAI-compatible, so LiteLLM cannot front them. They also carry each provider's voice catalog. |
| `pricing.py` | Per-character TTS cost. |
| `base.py` | The metadata contract for the registry. |

## Where the layer is called from

```
Voice Agents                              Voice inside workflows
─────────────                             ──────────────────────
api/rest/voice_sessions.py                nodes/transcribe_node.py
        │  (transport only)                       │
        ▼                                         ▼
services/voice_session_service.py         transcription.py::transcribe()
        │  resolves agent + key
        ▼                                 nodes/agent_voice.py
realtime/runtime.py                               │
        │                                         ▼
        ▼                                 realtime_dispatch.py / synthesis.py
bridge_dispatch.py::create_bridge()
```

Two things worth stating plainly, because both were violated once already:

- **The router is transport.** Assembling a session — reading the agent, inlining
  knowledge, resolving the provider key — belongs in `VoiceSessionService`, not in
  `api/rest/voice_sessions.py`.
- **The runtime holds no DB connection.** `load_voice_session_setup` opens a session,
  resolves everything, and releases it *before* audio starts. A call lasts minutes;
  a pooled connection must not.

## Adding a second conversation provider (e.g. Gemini Live)

1. `models/gemini.json` — the model entry with `"capability": "conversation"`.
2. `conversation_voices.py` — its voice list, if the provider has no listing endpoint.
3. `gemini_bridge.py` — implement `RealtimeBridge`, translating that provider's events
   into `BridgeEvent`. Nothing provider-shaped may cross that boundary.
4. `bridge_dispatch.py` — one branch.
5. `credentials_service.py` — add the provider to `_VOICE_PROVIDER_TO_CREDENTIALS_TYPE`,
   or a project's own key will be silently ignored in favour of the system key.

Step 5 is easy to forget and fails quietly. It already happened once with Gemini.
