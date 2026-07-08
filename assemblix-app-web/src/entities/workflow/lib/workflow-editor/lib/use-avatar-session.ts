import { useCallback, useRef, useState } from "react";
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
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rendererRef = useRef<AvatarRenderer | null>(null);
  const talkRef = useRef<AvatarTalkStream | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [mint] = useMintAvatarSessionMutation();

  const connect = useCallback(async () => {
    if (!videoRef.current || rendererRef.current) return;
    const session = await mint({ workflowId }).unwrap();
    const renderer = createRenderer(session.provider);
    await renderer.connect(session.sessionToken, videoRef.current);
    rendererRef.current = renderer;
    setIsConnected(true);
  }, [mint, workflowId]);

  const disconnect = useCallback(() => {
    talkRef.current?.end();
    talkRef.current = null;
    rendererRef.current?.disconnect();
    rendererRef.current = null;
    setIsConnected(false);
  }, []);

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
