# Analysis hooks

A voice agent can start ordinary workflows while it talks, and one more when it hangs
up. This is where the rest of Assemblix reaches the conversation: extract the caller's
details, write them to a CRM, score the call, raise an alert.

Two rules hold for both hooks:

- **The conversation never waits.** A hook runs in the background; the agent keeps
  talking.
- **The result does not come back.** In this version hooks observe, they do not steer.
  A workflow that fails is logged and dropped — it cannot end a call.

The workflows are normal workflows. Nothing about them is voice-specific, and you can
run and debug them by hand like any other.

## Per-turn workflow

Runs once for every finished thing the caller says.

```json
{
  "message": "I'd like to book an appointment for Tuesday",
  "voice": {
    "session_id": "…",
    "turn_index": 3,
    "agent_reply": "Of course — what day suits you?"
  }
}
```

`message` is the caller's utterance. `agent_reply` is what the agent said just before,
because a single utterance out of context is rarely enough to act on.

Reach these from a node with `input.message`, `input.voice.turn_index`, and so on.

## Final workflow

Runs once, after the call ends.

```json
{
  "message": "user: hello\nassistant: hi, how can I help?\n…",
  "voice": {
    "session_id": "…",
    "transcript": [{ "role": "user", "text": "hello" }],
    "duration_sec": 74.2,
    "end_reason": "user_hangup"
  }
}
```

`message` is the whole conversation flattened into text — usually what you want to hand
an agent node. `voice.transcript` is the same thing structured, for anything that needs
to walk the turns. `end_reason` is one of `user_hangup`, `timeout` or `error`.

## Reading the results

Every hook run is attached to the call that started it. Open a call from the agent's
**Calls** tab and its analysis runs are listed beside the transcript, each linking into
the execution viewer.
