import { useCallback, useEffect, useRef, useState } from "react";
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
  const [isConnected, setIsConnected] = useState(false);
  const [mint] = useMintAvatarSessionMutation();

  // Guards against the effect unmounting (or React StrictMode double-invoking
  // it) while `connect()` is still awaiting the mint/renderer.connect calls —
  // without it, a connect that resolves after unmount would store a live
  // renderer that disconnect() (already run by cleanup) never tears down.
  const cancelledRef = useRef(false);
  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  const disconnect = useCallback(() => {
    talkRef.current?.end();
    talkRef.current = null;
    rendererRef.current?.disconnect();
    rendererRef.current = null;
    setIsConnected(false);
  }, []);

  const connect = useCallback(async () => {
    if (!videoRef.current || rendererRef.current) return;
    let renderer: AvatarRenderer | null = null;
    try {
      const session = await mint({ workflowId }).unwrap();
      if (cancelledRef.current) return;
      renderer = createRenderer(session.provider);
      await renderer.connect(session.sessionToken, videoRef.current);
      if (cancelledRef.current) {
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

  // Forward one avatar-flagged STREAM_DELTA into the renderer, lazily opening
  // a talk stream on the first chunk of a reply.
  const onDelta = useCallback(({ avatar, delta }: AvatarStreamDelta) => {
    if (!avatar || !rendererRef.current) return;
    if (!talkRef.current) talkRef.current = rendererRef.current.speak();
    talkRef.current.chunk(delta);
  }, []);

  // Called when the avatar-emitting node's step completes: closes the talk
  // stream so the renderer knows the utterance is finished.
  const onAvatarNodeComplete = useCallback(() => {
    talkRef.current?.end();
    talkRef.current = null;
  }, []);

  return {
    videoRef,
    connect,
    disconnect,
    isConnected,
    onDelta,
    onAvatarNodeComplete,
  };
};
