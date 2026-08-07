# Voice agents

A **voice agent** answers a call. It is not a workflow: there is no canvas, no nodes, no
graph. You write a prompt, choose a voice, and the conversation runs directly against a
speech-to-speech model — the caller speaks, the model answers, and nothing sits between
them.

That is the whole point. A conversation that waits for a graph to finish sounds like a
conversation with someone reading from a script. A voice agent answers in roughly half a
second because the reasoning is not on the path to the reply.

## Voice agents are not voice in workflows

Both exist, and they are separate features:

| | Voice agent | Voice inside a workflow |
|---|---|---|
| Shape | a prompt and a voice | a graph with a `transcribe` node and an agent node that speaks |
| Turn | continuous, interruptible | one request, one answer |
| When | phone-like conversations | audio as an input or output of an automation |

Choosing one does not affect the other. See [Node types](../workflows/nodes.md) for the
workflow side.

## What you configure

**Agent** — the system prompt and, optionally, a first message. Leave the first message
empty and the agent waits for the caller to speak.

**Voice** — provider, model, voice and language. The trade-offs between providers are
real and worth reading before you pick: see [Providers](providers.md).

**Knowledge** — knowledge bases are inlined into the prompt once, when the call starts.
There is no retrieval mid-call, so there is no retrieval latency — but a long knowledge
base costs money on every call and slows the first reply. The character counter warns
you when the prompt gets expensive.

**Analysis** — up to two workflows that observe the conversation without shaping it.
See [Analysis hooks](analysis.md).

## Calls

Every call is recorded: its transcript, how long it lasted, what it cost, and every
analysis workflow it started. Open the **Calls** tab on the agent to read them back;
each analysis run links straight into the normal execution viewer.

Cost is charged by wall-clock time at the model's per-minute price, shown next to the
model when you pick it.

## Limits in this version

Voice agents are **test-in-editor only** for now: you call the agent from its page in
Assemblix. There is no public link, no embeddable widget and no telephony yet.
