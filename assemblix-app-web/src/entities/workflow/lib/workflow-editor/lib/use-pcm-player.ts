import { useCallback, useRef } from "react";

/**
 * Streaming PCM player for realtime voice output (phase 2b). Decodes base64 signed-16-bit
 * LE mono PCM chunks and schedules them back-to-back on a Web Audio graph for gapless
 * playback as `audio_delta` events arrive. Best-effort: decode/context errors are swallowed.
 */
export const usePcmPlayer = (sampleRate = 16000) => {
  const ctxRef = useRef<AudioContext | null>(null);
  const nextStartRef = useRef(0);

  const pushChunk = useCallback(
    (base64Pcm: string | undefined) => {
      if (!base64Pcm) return;
      try {
        const ctx = (ctxRef.current ??= new AudioContext());
        const binary = atob(base64Pcm);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const pcm16 = new Int16Array(bytes.buffer);
        const f32 = new Float32Array(pcm16.length);
        for (let i = 0; i < pcm16.length; i++) f32[i] = pcm16[i] / 32768;
        const buffer = ctx.createBuffer(1, f32.length, sampleRate);
        buffer.copyToChannel(f32, 0);
        const src = ctx.createBufferSource();
        src.buffer = buffer;
        src.connect(ctx.destination);
        const startAt = Math.max(ctx.currentTime, nextStartRef.current);
        src.start(startAt);
        nextStartRef.current = startAt + buffer.duration;
      } catch {
        // best-effort playback; ignore decode / audio-context errors
      }
    },
    [sampleRate],
  );

  const reset = useCallback(() => {
    nextStartRef.current = 0;
  }, []);

  return { pushChunk, reset };
};
