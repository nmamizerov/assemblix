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

export type CallStatus = "idle" | "connecting" | "live" | "ending";

export interface TranscriptLine {
  role: "user" | "assistant";
  text: string;
}

interface UseVoiceCallResult {
  status: CallStatus;
  transcript: TranscriptLine[];
  /** Last measured time from the caller's last audio frame to the agent's first. */
  firstAudioMs: number | null;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
}

export const useVoiceCall = (voiceAgentId: string): UseVoiceCallResult => {
  const [createSession] = useCreateVoiceSessionMutation();
  const player = usePcmPlayer(SAMPLE_RATE);

  const [status, setStatus] = useState<CallStatus>("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [firstAudioMs, setFirstAudioMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);

  const teardown = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void ctxRef.current?.close();
    ctxRef.current = null;
    player.flush();
    setStatus("idle");
  }, [player]);

  const handleControlFrame = useCallback(
    (frame: Record<string, unknown>) => {
      switch (frame.type) {
        case "session.ready":
          setStatus("live");
          break;
        case "transcript": {
          if (!frame.isFinal) return;
          setTranscript((lines) => [
            ...lines,
            { role: frame.role as TranscriptLine["role"], text: String(frame.text) },
          ]);
          break;
        }
        case "speech.started":
          // The user cut in: drop everything already queued so the agent stops
          // mid-word instead of finishing a sentence nobody is listening to.
          player.flush();
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
    setFirstAudioMs(null);

    try {
      const { token } = await createSession(voiceAgentId).unwrap();

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

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
          player.pushPcm(event.data);
          return;
        }
        handleControlFrame(JSON.parse(event.data));
      };
      socket.onerror = () => setError("connection");
      socket.onclose = () => teardown();

      const recorder = new AudioWorkletNode(ctx, "pcm-recorder");
      recorder.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
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
      setError(cause instanceof Error ? cause.message : "call_failed");
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

  useEffect(() => teardown, [teardown]);

  return { status, transcript, firstAudioMs, error, start, stop };
};
