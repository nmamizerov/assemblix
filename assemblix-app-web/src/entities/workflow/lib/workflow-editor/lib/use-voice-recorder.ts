import { useCallback, useRef, useState } from "react";
import {
  MediaRecorder as WavMediaRecorder,
  register,
} from "extendable-media-recorder";
import { connect } from "extendable-media-recorder-wav-encoder";

export type VoiceRecorderState = "idle" | "recording" | "error";

export interface RecordedAudio {
  blob: Blob;
  filename: string;
}

interface UseVoiceRecorderResult {
  state: VoiceRecorderState;
  isRecording: boolean;
  error: string | null;
  start: () => Promise<void>;
  stop: () => Promise<RecordedAudio | null>;
  cancel: () => void;
}

// We record straight to WAV instead of the browser's native MediaRecorder WebM.
// MediaRecorder emits streaming WebM/Opus with an incomplete header (no Duration/
// Cues); OpenAI's gpt-4o-transcribe validator rejects that as "corrupted or
// unsupported" (whisper-1 is lenient and tolerates it). A WAV has a fully-formed
// RIFF header written on finalize, so every transcription provider accepts it —
// this is the browser-side, ffmpeg-free fix. The wav encoder must be registered
// exactly once per document; register() throws on a second call, so memoize it.
let wavEncoderRegistration: Promise<void> | null = null;
const ensureWavEncoder = (): Promise<void> => {
  if (!wavEncoderRegistration) {
    wavEncoderRegistration = connect().then((port) => register(port));
  }
  return wavEncoderRegistration;
};

/**
 * Records a short audio clip via getUserMedia + a WAV-encoding MediaRecorder.
 * Transport-agnostic: it returns a Blob, so callers decide how to send it (today:
 * multipart upload to /execute/debug/audio; later a realtime stream could swap in
 * under the same UI).
 */
export const useVoiceRecorder = (): UseVoiceRecorderResult => {
  const [state, setState] = useState<VoiceRecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<InstanceType<typeof WavMediaRecorder> | null>(
    null,
  );
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const cleanup = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      await ensureWavEncoder();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1 },
      });
      streamRef.current = stream;

      const recorder = new WavMediaRecorder(stream, { mimeType: "audio/wav" });
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.start();
      recorderRef.current = recorder;
      setState("recording");
    } catch (err) {
      cleanup();
      setState("error");
      setError(err instanceof Error ? err.message : "Microphone access failed");
    }
  }, [cleanup]);

  const stop = useCallback(async (): Promise<RecordedAudio | null> => {
    const recorder = recorderRef.current;
    if (!recorder) return null;

    const blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () =>
        resolve(new Blob(chunksRef.current, { type: "audio/wav" }));
      recorder.stop();
    });
    cleanup();
    setState("idle");

    if (blob.size === 0) return null;
    return { blob, filename: "voice.wav" };
  }, [cleanup]);

  const cancel = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null;
      recorder.stop();
    }
    cleanup();
    setState("idle");
  }, [cleanup]);

  return {
    state,
    isRecording: state === "recording",
    error,
    start,
    stop,
    cancel,
  };
};
