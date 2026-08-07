import { useCallback, useEffect, useRef, useState } from "react";

import { usePcmPlayer } from "@/shared/lib/use-pcm-player";

import { useCreateVoiceSessionMutation } from "../api/voice-agent.api";

// The provider takes PCM16 mono at this rate. The browser reaches it natively —
// an AudioContext created with this sampleRate resamples the microphone stream
// itself — so nothing here converts sample rates by hand.
const SAMPLE_RATE = 24000;

// Served from public/ rather than bundled: `?url` turns the worklet into a
// data: URL, which addModule rejects under a strict CSP and on some browsers.
const WORKLET_URL = "/pcm-recorder.worklet.js";

// A call that has not gone live by now is stuck — usually a microphone prompt
// nobody answered, or a WebSocket the proxy never upgraded. Failing loudly beats
// a spinner that turns forever.
const CONNECT_TIMEOUT_MS = 15000;

const micErrorKey = (cause: unknown): string => {
  const name = cause instanceof Error ? cause.name : "";
  if (name === "NotAllowedError") return "micDenied";
  if (name === "NotFoundError") return "micMissing";
  return "micFailed";
};

export type CallStatus = "idle" | "connecting" | "live" | "ending";

export interface TranscriptLine {
  role: "user" | "assistant";
  text: string;
}

/**
 * Live loudness of each side, 0..1. Read through a ref rather than state: this
 * updates ~50 times a second and only the visualizer's animation frame cares,
 * so pushing it through React would re-render the page for nothing.
 */
export interface CallLevels {
  user: number;
  agent: number;
}

interface UseVoiceCallResult {
  status: CallStatus;
  transcript: TranscriptLine[];
  /** The sentence being spoken right now, before the provider finalizes it. */
  interim: TranscriptLine | null;
  /** Last measured time from the caller's last audio frame to the agent's first. */
  firstAudioMs: number | null;
  error: string | null;
  levels: React.RefObject<CallLevels>;
  start: () => Promise<void>;
  stop: () => void;
}

/** Root-mean-square of a PCM16 frame, normalized to 0..1. */
const frameLevel = (pcm: Int16Array): number => {
  if (pcm.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < pcm.length; i++) sum += pcm[i] * pcm[i];
  return Math.min(1, Math.sqrt(sum / pcm.length) / 8000);
};

export const useVoiceCall = (voiceAgentId: string): UseVoiceCallResult => {
  const [createSession] = useCreateVoiceSessionMutation();
  const player = usePcmPlayer(SAMPLE_RATE);

  const [status, setStatus] = useState<CallStatus>("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [interim, setInterim] = useState<TranscriptLine | null>(null);
  const [firstAudioMs, setFirstAudioMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const levels = useRef<CallLevels>({ user: 0, agent: 0 });

  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const watchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const teardown = useCallback(() => {
    if (watchdogRef.current) clearTimeout(watchdogRef.current);
    watchdogRef.current = null;
    socketRef.current?.close();
    socketRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void ctxRef.current?.close();
    ctxRef.current = null;
    player.flush();
    levels.current.user = 0;
    levels.current.agent = 0;
    setInterim(null);
    setStatus("idle");
  }, [player]);

  const handleControlFrame = useCallback(
    (frame: Record<string, unknown>) => {
      switch (frame.type) {
        case "session.ready":
          if (watchdogRef.current) clearTimeout(watchdogRef.current);
          watchdogRef.current = null;
          setStatus("live");
          break;
        case "transcript": {
          const line = {
            role: frame.role as TranscriptLine["role"],
            text: String(frame.text),
          };
          if (!frame.isFinal) {
            setInterim(line);
            return;
          }
          setInterim(null);
          setTranscript((lines) => [...lines, line]);
          break;
        }
        case "speech.started":
          // The user cut in: drop everything already queued so the agent stops
          // mid-word instead of finishing a sentence nobody is listening to.
          player.flush();
          levels.current.agent = 0;
          break;
        case "turn.timings":
          setFirstAudioMs(Number(frame.firstAudioMs));
          break;
        case "error":
          setError(String(frame.message));
          break;
        case "session.closed":
          teardown();
          break;
      }
    },
    [player, teardown],
  );

  const start = useCallback(async () => {
    if (status !== "idle") return;
    setStatus("connecting");
    setError(null);
    setTranscript([]);
    setInterim(null);
    setFirstAudioMs(null);

    // Ask for the microphone first, while the click gesture is still fresh, and
    // before a token is minted that a denied prompt would waste.
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;
    } catch (cause) {
      console.error(cause);
      setError(micErrorKey(cause));
      teardown();
      return;
    }

    watchdogRef.current = setTimeout(() => {
      setError("timeout");
      teardown();
    }, CONNECT_TIMEOUT_MS);

    try {
      const { token } = await createSession(voiceAgentId).unwrap();

      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      ctxRef.current = ctx;
      await ctx.audioWorklet.addModule(WORKLET_URL);

      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(
        `${scheme}://${window.location.host}/api/voice-agents/sessions/${token}/stream`,
      );
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;

      socket.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          // The visualizer is driven by the audio itself, so the loudness is
          // measured here rather than through a second analyser node.
          levels.current.agent = frameLevel(new Int16Array(event.data));
          player.pushPcm(event.data);
          return;
        }
        handleControlFrame(JSON.parse(event.data));
      };
      socket.onerror = () => setError("connectFailed");
      socket.onclose = () => teardown();

      const recorder = new AudioWorkletNode(ctx, "pcm-recorder");
      recorder.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
        levels.current.user = frameLevel(new Int16Array(event.data));
        if (socket.readyState === WebSocket.OPEN) socket.send(event.data);
      };
      ctx.createMediaStreamSource(stream).connect(recorder);
      // A worklet only runs while it is connected to the graph, but the captured
      // microphone must never reach the speakers — route it through a muted gain.
      const muted = ctx.createGain();
      muted.gain.value = 0;
      recorder.connect(muted).connect(ctx.destination);
    } catch (cause) {
      console.error(cause);
      setError("connectFailed");
      teardown();
    }
  }, [createSession, handleControlFrame, player, status, teardown, voiceAgentId]);

  const stop = useCallback(() => {
    setStatus("ending");
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: "session.stop" }));
    }
    teardown();
  }, [teardown]);

  // Unmount only. Depending on `teardown` directly would re-run this cleanup
  // every time its identity changed — which killed the call on the first
  // re-render after start().
  const teardownRef = useRef(teardown);
  useEffect(() => {
    teardownRef.current = teardown;
  }, [teardown]);
  useEffect(() => () => teardownRef.current(), []);

  return { status, transcript, interim, firstAudioMs, error, levels, start, stop };
};
