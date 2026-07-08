import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useMintAvatarSessionMutation } from "@/entities/avatar-model";
import { createRenderer, type AvatarRenderer, type AvatarTalkStream } from "./avatar-renderer";

export interface AvatarStreamDelta {
  avatar: boolean;
  delta: string;
}

// Orchestrates the client-side avatar session: mints a short-lived token from
// the backend, connects the provider renderer to a <video> element, and
// forwards avatar-flagged text deltas from the streaming run into the
// renderer's talk stream (lip-sync). See avatar-renderer/ (Task 14) for the
// provider-specific implementation.
export const useAvatarSession = (workflowId: string) => {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rendererRef = useRef<AvatarRenderer | null>(null);
  const talkRef = useRef<AvatarTalkStream | null>(null);
  // Buffers the start of a reply until it forms a phrase before opening the talk
  // stream — sending single tokens as the first chunk makes the TTS engine clip
  // the opening words while it warms up.
  const pendingRef = useRef("");
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
    pendingRef.current = "";
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

  // Open the talk stream with the buffered lead-in text (first phrase of a reply).
  const flushPending = useCallback(() => {
    if (!rendererRef.current || !pendingRef.current) return;
    talkRef.current = rendererRef.current.speak();
    talkRef.current.chunk(pendingRef.current);
    pendingRef.current = "";
  }, []);

  // Forward one avatar-flagged STREAM_DELTA into the renderer. Buffer the reply's
  // start until it forms a phrase (a boundary char or ~20 chars), then stream the
  // rest directly — avoids the TTS engine clipping the opening words.
  const onDelta = useCallback(
    ({ avatar, delta }: AvatarStreamDelta) => {
      if (!avatar || !rendererRef.current) return;
      if (talkRef.current) {
        talkRef.current.chunk(delta);
        return;
      }
      pendingRef.current += delta;
      if (pendingRef.current.length >= 20 || /[.!?\n]/.test(pendingRef.current)) {
        flushPending();
      }
    },
    [flushPending],
  );

  // Called when the avatar-emitting node's step completes: flush any lead-in that
  // never reached the threshold (short reply), then close the talk stream.
  const onAvatarNodeComplete = useCallback(() => {
    if (!talkRef.current) flushPending();
    talkRef.current?.end();
    talkRef.current = null;
    pendingRef.current = "";
  }, [flushPending]);

  // Diagnostic: make the avatar speak a fixed phrase directly, bypassing the
  // workflow — isolates the provider talk path from the streaming pipeline.
  const testSpeak = useCallback((text: string) => {
    if (!rendererRef.current) return;
    const stream = rendererRef.current.speak();
    stream.chunk(text);
    stream.end();
  }, []);

  return {
    videoRef,
    connect,
    disconnect,
    isConnected,
    onDelta,
    onAvatarNodeComplete,
    testSpeak,
  };
};
