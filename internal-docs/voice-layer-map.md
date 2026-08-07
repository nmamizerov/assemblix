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
| `speech` | text → audio (one blob) | `synthesis.py::synthesize()` | `providers/elevenlabs.py`, `providers/yandex.py` | agent node, buffered voice output |
| `realtime` (pkg `streaming_tts/`) | text → audio (streamed) | `streaming_tts/__init__.py::create_realtime_session()` | `streaming_tts/elevenlabs.py`, `streaming_tts/yandex.py` | agent node with live voice, avatars |
| `conversation` | audio ↔ audio (duplex) | `conversation/__init__.py::create_bridge()` | `conversation/openai.py`, `conversation/gemini.py` | **Voice Agents** |

### The name trap

`streaming_tts` and `conversation` sound like the same thing. They are opposites:

```
streaming_tts  text  ─────────►  audio          the agent writes, we speak it
conversation   audio ◄────────►  audio          the caller speaks, the model answers
```

`streaming_tts` belongs to **voice inside workflows**. `conversation` belongs to **Voice
Agents**. They share nothing but the folder.

## How a capability is wired

Every capability follows the same three layers. Using `conversation` as the example:

```
       caller (runtime / node)
                │
                │  knows only the seam
                ▼
   conversation/__init__.py      create_bridge(provider=...) → RealtimeBridge
                │                 raises NotImplementedError for unknown providers
                │
                ▼
   conversation/contract.py      the contract: RealtimeBridge protocol
                │                 + BridgeEvent, the normalized event vocabulary
                │
                ▼
   conversation/openai.py        the only file that imports the `openai` SDK
```

The rule this encodes: **provider vocabulary stops at the seam.** Above
`conversation/__init__`, nothing knows whether it is talking to OpenAI or anyone else. The
same shape holds for `streaming_tts/` → its two session classes, and for
`synthesis.py` / `transcription.py` → their providers.

## The registry

```
   catalog/registry.py ──reads──► catalog/models/openai.json
                                  catalog/models/gemini.json
                                  catalog/models/elevenlabs.json
                                  catalog/models/yandex.json
```

`catalog/registry.py` answers "which providers and models exist, for which capability,
at what price". The JSON files are the data; `catalog/metadata.py` is the type they are validated
against (`VoiceModelMetadata`: id, label, capability, route, cost).

**Adding a model is a JSON edit.** Adding a provider is a JSON file plus an entry in
`VOICE_PROVIDER_LABELS`, plus a branch in the relevant dispatcher if it needs one.

The catalog is what the frontend's provider/model pickers read, through
`/api/voice/providers?capability=…`.

## Everything else

| File | What it is |
|---|---|
| `conversation/voices.py` | Static voice (timbre) lists for OpenAI and Gemini. Static because neither exposes a voice-listing endpoint — same reason `yandex.py` hardcodes its own. |
| `providers/elevenlabs.py`, `providers/yandex.py` | Direct clients for providers that are **not** OpenAI-compatible, so LiteLLM cannot front them. They also carry each provider's voice catalog. |
| `pricing.py` | Per-character TTS cost. |
| `catalog/metadata.py` | The metadata contract for the registry. |

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
        ▼                                 streaming_tts/ / synthesis.py
conversation/__init__.py::create_bridge()
```

Two things worth stating plainly, because both were violated once already:

- **The router is transport.** Assembling a session — reading the agent, inlining
  knowledge, resolving the provider key — belongs in `VoiceSessionService`, not in
  `api/rest/voice_sessions.py`.
- **The runtime holds no DB connection.** `load_voice_session_setup` opens a session,
  resolves everything, and releases it *before* audio starts. A call lasts minutes;
  a pooled connection must not. The only other two moments that touch the database are
  `open_voice_session` (before the first frame, so hooks have an FK target) and
  `close_voice_session` (after the last), each with its own short-lived session.
- **Hooks are never awaited during the call.** `realtime/hooks.py::TurnDispatcher` fires
  the per-turn workflow through the ordinary `run_workflow_isolated` path and drops the
  task; a hook that raises is logged and forgotten. Only the final hook is awaited, and
  only once the call is already over.

## Adding a conversation provider

Walked twice now — OpenAI, then Gemini Live. The long-form version, written against
the Gemini integration, is [CONTRIBUTING_VOICE_AGENTS.md](CONTRIBUTING_VOICE_AGENTS.md).

1. `catalog/models/<provider>.json` — the model entry with `"capability": "conversation"`
   and a `costPerMinute` (a call is billed by wall-clock, so this number is the charge).
2. `conversation/voices.py` — its voice list, if the provider has no listing endpoint.
3. `conversation/<provider>.py` — implement `RealtimeBridge`, translating that provider's
   events into `BridgeEvent`. Nothing provider-shaped may cross that boundary. Declare
   `input_sample_rate` / `output_sample_rate` honestly: they are part of the contract and
   travel to the browser, which builds its capture and playback graphs from them.
4. `conversation/__init__.py` — one branch.
5. `credentials_service.py` — add the provider to `_VOICE_PROVIDER_TO_CREDENTIALS_TYPE`,
   or a project's own key will be silently ignored in favour of the system key.

Step 5 is easy to forget and fails quietly. It already happened once with Gemini.
