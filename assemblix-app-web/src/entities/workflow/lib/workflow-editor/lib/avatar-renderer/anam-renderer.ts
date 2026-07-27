import { createClient, type AnamClient } from "@anam-ai/js-sdk";

import type { AvatarAudioStream, AvatarRenderer } from "./types";

// Matches the backend realtime PCM wire format (`pcm_16000`): 16-bit signed
// little-endian, 16 kHz, mono. sendAudioChunk accepts the base64 string as-is.
const AUDIO_CONFIG = {
  encoding: "pcm_s16le",
  sampleRate: 16000,
  channels: 1,
} as const;

export const createAnamRenderer = (): AvatarRenderer => {
  let client: AnamClient | null = null;

  return {
    async connect(sessionToken, videoEl) {
      // disableInputAudio: we drive the avatar with our own audio (passthrough),
      // so anam must not capture the microphone or synthesize its own voice.
      client = createClient(sessionToken, { disableInputAudio: true });
      videoEl.id = videoEl.id || "anam-avatar-video";
      await client.streamToVideoElement(videoEl.id);
    },
    speak(): AvatarAudioStream {
      if (!client) throw new Error("Anam renderer not connected");
      const stream = client.createAgentAudioInputStream(AUDIO_CONFIG);
      return {
        chunk: (base64Pcm) => stream.sendAudioChunk(base64Pcm),
        end: () => stream.endSequence(),
      };
    },
    disconnect() {
      if (!client) return;
      client.stopStreaming().catch((error: unknown) => {
        console.error("anam avatar stop error", error);
      });
      client = null;
    },
  };
};
