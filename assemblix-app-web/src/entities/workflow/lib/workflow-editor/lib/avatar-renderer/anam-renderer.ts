import { createClient, type AnamClient } from "@anam-ai/js-sdk";

import type { AvatarRenderer, AvatarTalkStream } from "./types";

// Anam's client methods (streamMessageChunk/endMessage/stopStreaming) return
// Promise<void>; the AvatarRenderer interface is fire-and-forget, so we don't
// await them here, but rejections are still logged instead of swallowed.
const fireAndForget = (promise: Promise<void>): void => {
  promise.catch((error: unknown) => {
    console.error("anam avatar stream error", error);
  });
};

export const createAnamRenderer = (): AvatarRenderer => {
  let client: AnamClient | null = null;

  return {
    async connect(sessionToken, videoEl) {
      client = createClient(sessionToken);
      videoEl.id = videoEl.id || "anam-avatar-video";
      await client.streamToVideoElement(videoEl.id);
    },
    speak(): AvatarTalkStream {
      if (!client) throw new Error("Anam renderer not connected");
      const stream = client.createTalkMessageStream();
      return {
        chunk: (text) => fireAndForget(stream.streamMessageChunk(text, false)),
        end: () => fireAndForget(stream.endMessage()),
      };
    },
    disconnect() {
      if (!client) return;
      fireAndForget(client.stopStreaming());
      client = null;
    },
  };
};
