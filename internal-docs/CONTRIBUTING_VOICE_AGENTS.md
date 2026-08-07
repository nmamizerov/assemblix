# Adding a speech-to-speech provider to Voice Agents

Sibling of [CONTRIBUTING_NODES.md](CONTRIBUTING_NODES.md). This describes a path that
has been walked twice: OpenAI Realtime first, then Gemini Live — and the second one is
what shaped this document, because it broke assumptions the first had quietly baked in.

Read [voice-layer-map.md](voice-layer-map.md) first. `conversation/` (audio ↔ audio) and
`streaming_tts/` (text → audio) sound alike and are opposites.

## The five steps

### 1. Catalog entry

`assemblix-app-api/assemblix_api/external/voice/catalog/models/<provider>.json`:

```json
{ "models": [{
  "id": "gemini-3.1-flash-live-preview",
  "label": "Gemini 3.1 Flash Live",
  "capability": "conversation",
  "route": "conversation",
  "costPerMinute": 0.03
}] }
```

`costPerMinute` is not decoration — a call is billed by wall-clock, so this is literally
the charge. A missing value means the calls are free.

If the provider is new to the platform, add it to `VOICE_PROVIDER_LABELS` too; without
that entry the model is invisible even with a JSON file present.

### 2. Voices

Neither OpenAI nor Google exposes a voice-listing endpoint for realtime models, so
`conversation/voices.py` holds a static tuple per provider. Ids are usually
case-sensitive.

### 3. The bridge

`conversation/<provider>.py` implements `RealtimeBridge` and is **the only file allowed
to import that provider's SDK**. Take a `connect_factory` argument: it is what makes the
adapter testable without a network.

Declare the rates honestly:

```python
class GeminiLiveBridge:
    input_sample_rate = 16000     # what the browser must send
    output_sample_rate = 24000    # what this bridge emits
```

These are contract, not trivia. The runtime reads them off the bridge and forwards them
in `session.ready`; the browser builds its capture graph at `inputSampleRate` and plays
back at `outputSampleRate`. Nothing anywhere resamples. Getting this wrong produces
audio that is subtly fast or slow rather than an error.

Then translate events. The vocabulary is fixed — `AudioDelta`, `UserTranscript`,
`AgentTranscript`, `SpeechStarted`, `TurnEnded`, `BridgeError`, `SessionClosed` — and
the runtime above never learns which provider produced them.

**Where providers actually differ, from the two integrations so far:**

| | OpenAI Realtime | Gemini Live |
|---|---|---|
| Rates | 24 kHz both ways | 16 kHz in, 24 kHz out |
| Barge-in | client sends `response.cancel` + `conversation.item.truncate` | server-side; `interrupt()` is a no-op, `server_content.interrupted` reports it after the fact |
| Transcript | `…transcription.completed` carries the whole sentence | fragments only; the adapter accumulates and finalizes |
| Event stream | one long iterator | `receive()` ends on every `turn_complete` — wrap it in an outer loop or the call hangs up after the first answer |
| Usage | `response.done.usage` | message-level `usage_metadata` |

All five differences are absorbed inside the adapter. If one of them is leaking upward,
the abstraction is wrong, not the provider.

### 4. The factory branch

`conversation/__init__.py` — one `if provider == …` line.

### 5. Credentials mapping

`services/credentials_service.py` → `_VOICE_PROVIDER_TO_CREDENTIALS_TYPE`. Forget this
and a project's own key is silently ignored in favour of the system key: no error, no
log, just someone else's bill. It has already happened once.

## Testing

Test the adapter, not the SDK. Build `LiveServerMessage`-shaped frames (or the OpenAI
equivalent), inject a fake session through `connect_factory`, drain `events()`, and
assert the exact `BridgeEvent` sequence — including the ones the provider does not send
explicitly, such as a reply finalized by `turn_complete`.

`tests/unit/external/test_conversation_gemini.py` is the worked example. The
runtime-level counterpart, `tests/integration/test_voice_session_hooks.py`, drives a
fake bridge through a whole call and is where hook and metering behaviour is pinned.
