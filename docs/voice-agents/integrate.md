# Integrating a call

The test panel on the agent page is a client like any other. This page describes the
protocol it speaks, so you can build your own.

The shape is two steps:

1. **Your backend** mints a short-lived session token with your project API key.
2. **Your frontend** opens a WebSocket with that token and streams audio both ways.

The key never reaches the browser, and the token is useless a minute after it is issued.

## 1. Mint a session token

```bash
curl -X POST https://api.assemblix.ai/api/voice-agents/{voiceAgentId}/sessions \
  -H "Authorization: Bearer sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

```json
{ "token": "eyJhbGciOi…", "expiresIn": 60 }
```

Do this from your server, in response to a request from your own authenticated user —
the token authorizes exactly one call with one agent, and anyone holding it can place
that call. Mint it when the user presses the button, not when the page loads: it expires
in 60 seconds, and that short life is the whole security model.

The agent must be active; an inactive one returns `400`.

## 2. Open the socket

```
wss://api.assemblix.ai/api/voice-agents/sessions/{token}/stream
```

No headers, no auth — the token is in the path, which is what makes this work from a
browser (a WebSocket handshake cannot carry an `Authorization` header).

### What you send

| Frame | Meaning |
|---|---|
| **binary** | PCM16 mono, little-endian, at `inputSampleRate` |
| `{"type": "session.stop"}` | Hang up |

### What you receive

| Frame | Meaning |
|---|---|
| `{"type":"session.ready","inputSampleRate":N,"outputSampleRate":N}` | The provider is connected. **Do not send audio before this.** |
| **binary** | The agent's speech, PCM16 mono at `outputSampleRate` |
| `{"type":"transcript","role":"user"\|"assistant","text":"…","isFinal":bool}` | Live captions. Non-final frames replace the previous one; final frames are a completed line. |
| `{"type":"speech.started"}` | The caller cut in. **Drop everything you have queued for playback.** |
| `{"type":"turn.timings","firstAudioMs":N}` | Last inbound audio → first audio back, for this turn |
| `{"type":"error","code":…,"message":…,"isFatal":bool}` | A non-fatal error is worth logging and nothing more |
| `{"type":"session.closed","reason":"…"}` | Terminal. `user_hangup`, `timeout`, `error`, `completed` or `provider_closed`. |

## Sample rates are not a constant

`session.ready` tells you the rates, and they differ by provider: OpenAI Realtime is
24 kHz in both directions, Gemini Live listens at 16 kHz and answers at 24 kHz. Switching
an agent's provider changes them under you.

Do not resample. Build the capture graph at `inputSampleRate` and play back at
`outputSampleRate`, and the browser converts natively:

```js
const capture = new AudioContext({ sampleRate: inputSampleRate });
```

This is also why capture must start *after* `session.ready` rather than while the socket
is opening.

## Barge-in

An `AudioBufferSourceNode` plays to its end once started. Advancing your schedule
pointer is not enough — on `speech.started` you have to call `stop()` on every source
already queued, or the agent keeps talking over the caller for however many seconds you
had buffered. This one detail is the difference between a call that feels alive and one
that feels like a voicemail system.

## A working client

```js
async function call(voiceAgentId) {
  // 1. Your own backend, which holds the project key and mints the token.
  const { token } = await fetch(`/api/voice-token/${voiceAgentId}`).then(r => r.json());

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });

  const socket = new WebSocket(
    `wss://api.assemblix.ai/api/voice-agents/sessions/${token}/stream`
  );
  socket.binaryType = "arraybuffer";

  const playback = new AudioContext();
  let playAt = 0;
  const queued = new Set();

  const play = (pcm16, rate) => {
    const f32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) f32[i] = pcm16[i] / 32768;
    const buffer = playback.createBuffer(1, f32.length, rate);
    buffer.copyToChannel(f32, 0);

    const src = playback.createBufferSource();
    src.buffer = buffer;
    src.connect(playback.destination);
    queued.add(src);
    src.onended = () => queued.delete(src);

    const startAt = Math.max(playback.currentTime, playAt);
    src.start(startAt);
    playAt = startAt + buffer.duration;
  };

  const flush = () => {
    for (const src of queued) { try { src.stop(); } catch {} }
    queued.clear();
    playAt = 0;
  };

  let outputRate = 24000;

  socket.onmessage = async (event) => {
    if (event.data instanceof ArrayBuffer) {
      play(new Int16Array(event.data), outputRate);
      return;
    }
    const frame = JSON.parse(event.data);

    if (frame.type === "session.ready") {
      outputRate = frame.outputSampleRate;
      await startCapture(frame.inputSampleRate, stream, socket);
    } else if (frame.type === "speech.started") {
      flush();                                   // the caller cut in
    } else if (frame.type === "transcript" && frame.isFinal) {
      console.log(`${frame.role}: ${frame.text}`);
    } else if (frame.type === "session.closed") {
      stream.getTracks().forEach(t => t.stop());
      playback.close();
    }
  };

  return () => socket.send(JSON.stringify({ type: "session.stop" }));
}
```

`startCapture` builds an `AudioContext` at the given rate, loads an
[AudioWorklet](https://developer.mozilla.org/docs/Web/API/AudioWorklet) that converts
float samples to PCM16, and posts roughly 200 ms per frame to the socket. Keep it in a
worklet rather than a `ScriptProcessorNode`: capture on the main thread stutters the
moment your UI does anything.

Route the worklet through a **muted** gain node into the destination. A worklet only
runs while it is connected to the graph, but the captured microphone must never reach
the speakers.

## Reading the call back

Every call is recorded, whoever placed it:

```
GET /api/voice-agents/{voiceAgentId}/sessions?page=1&limit=50
GET /api/voice-sessions/{voiceSessionId}
```

The detail response carries the transcript, duration, cost, and every analysis workflow
the call started — each with an execution id you can open through the normal execution
API. See [Analysis hooks](analysis.md) for what those workflows receive.

Calls placed with a project API key are marked as real; calls placed from the editor are
marked `isDebug`, so your dashboards can tell rehearsals from customers.

## Limits

- One token, one call. Re-mint for each.
- A call is capped by the server's session wall-clock limit; when it hits, you get
  `session.closed` with `reason: "timeout"`.
- No telephony (SIP) and no drop-in widget yet. The protocol above is what there is.
