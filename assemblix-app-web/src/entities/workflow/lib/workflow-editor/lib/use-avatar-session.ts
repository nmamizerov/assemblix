import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useMintAvatarSessionMutation } from "@/entities/avatar-model";
import { createRenderer, type AvatarRenderer, type AvatarAudioStream } from "./avatar-renderer";

// Orchestrates the client-side avatar session: mints a short-lived token from the
// backend, connects the provider renderer to a <video> element, and feeds the
// avatar-flagged realtime PCM chunks from the streaming run into the renderer's
// audio-passthrough stream (the avatar lip-syncs to — and plays — that audio).
// See avatar-renderer/ for the provider-specific implementation.
export const useAvatarSession = (workflowId: string) => {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rendererRef = useRef<AvatarRenderer | null>(null);
  const talkRef = useRef<AvatarAudioStream | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [mint] = useMintAvatarSessionMutation();

  // Per-invocation epoch guards against the effect unmounting (or React
  // StrictMode double-invoking it) while `connect()` is still awaiting the
  // mint/renderer.connect calls. A component-scoped boolean flag isn't
  // enough here: a cleanup that resets the flag on remount would make an
  // in-flight call from the *previous* mount believe it's still valid,
  // letting it store a second live renderer. Each connect() call captures
  // the epoch at its start; disconnect() (and a fresh connect()) bumps it,
  // invalidating any older in-flight call so it tears itself down instead
  // of storing its renderer.
  const connectEpochRef = useRef(0);

  const disconnect = useCallback(() => {
    connectEpochRef.current += 1;
    talkRef.current?.end();
    talkRef.current = null;
    rendererRef.current?.disconnect();
    rendererRef.current = null;
    setIsConnected(false);
  }, []);

  const connect = useCallback(async () => {
    if (!videoRef.current || rendererRef.current) return;
    const myEpoch = ++connectEpochRef.current;
    let renderer: AvatarRenderer | null = null;
    try {
      const session = await mint({ workflowId }).unwrap();
      if (connectEpochRef.current !== myEpoch) return;
      renderer = createRenderer(session.provider);
      await renderer.connect(session.sessionToken, videoRef.current);
      if (connectEpochRef.current !== myEpoch) {
        renderer.disconnect();
        return;
      }
      rendererRef.current = renderer;
      setIsConnected(true);
    } catch (err) {
      console.error("Error connecting avatar session:", err);
      renderer?.disconnect();
      rendererRef.current = null;
      setIsConnected(false);
      toast.error(t("nodeForms.avatar.connectError"));
    }
  }, [mint, workflowId, t]);

  // Forward one avatar-flagged AUDIO_DELTA (base64 PCM) into the renderer. Opens the
  // talk stream lazily on the first chunk of an utterance. Anam buffers chunks
  // internally and renders lip-sync as they arrive.
  const onAudioChunk = useCallback((base64Pcm: string) => {
    if (!rendererRef.current || !base64Pcm) return;
    if (!talkRef.current) talkRef.current = rendererRef.current.speak();
    talkRef.current.chunk(base64Pcm);
  }, []);

  // Called when the avatar-emitting node's step completes: close the audio sequence
  // so the renderer knows the utterance ended.
  const onAvatarNodeComplete = useCallback(() => {
    talkRef.current?.end();
    talkRef.current = null;
  }, []);

  return {
    videoRef,
    connect,
    disconnect,
    isConnected,
    onAudioChunk,
    onAvatarNodeComplete,
  };
};
