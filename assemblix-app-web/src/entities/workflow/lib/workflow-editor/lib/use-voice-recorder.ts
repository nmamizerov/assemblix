import { useCallback, useRef, useState } from "react";

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

// Pick a container the browser can actually record: Chrome/Firefox → webm/opus,
// Safari → mp4. Both are accepted by the backend transcription providers.
const pickMimeType = (): string | undefined => {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm", "audio/mp4", "audio/ogg"].find((type) =>
    MediaRecorder.isTypeSupported(type)
  );
};

const extensionFor = (mimeType: string): string => {
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("mp4")) return "mp4";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
};

/**
 * Records a short audio clip via getUserMedia + MediaRecorder. Transport-agnostic:
 * it returns a Blob, so callers decide how to send it (today: multipart upload to
 * /execute/debug/audio; later a realtime stream could swap in under the same UI).
 */
export const useVoiceRecorder = (): UseVoiceRecorderResult => {
  const [state, setState] = useState<VoiceRecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
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
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined
      );
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

    const mimeType = recorder.mimeType || "audio/webm";
    const blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () =>
        resolve(new Blob(chunksRef.current, { type: mimeType }));
      recorder.stop();
    });
    cleanup();
    setState("idle");

    if (blob.size === 0) return null;
    return { blob, filename: `voice.${extensionFor(mimeType)}` };
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
