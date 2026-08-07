import { useCallback, useEffect, useMemo, useRef } from "react";

/**
 * Streaming PCM player. Decodes signed-16-bit LE mono chunks and schedules them
 * back-to-back on a Web Audio graph for gapless playback.
 *
 * `sampleRate` describes the incoming audio, not the output device: each buffer
 * carries its own rate and the browser resamples it. Forcing the context to that
 * rate instead makes some devices fail outright with a WebAudio renderer error.
 * It is held in a ref and changed through `setSampleRate` because the rate is
 * only known once the server names it — and re-creating this object mid-call
 * would tear down the handlers a live session is running on.
 *
 * `flush` is what makes barge-in work: an AudioBufferSourceNode plays to the end
 * once started, so dropping the schedule pointer is not enough — every source
 * already queued has to be stopped explicitly.
 */
export const usePcmPlayer = (sampleRate = 16000) => {
  const ctxRef = useRef<AudioContext | null>(null);
  const nextStartRef = useRef(0);
  const rateRef = useRef(sampleRate);
  const scheduledRef = useRef(new Set<AudioBufferSourceNode>());

  const setSampleRate = useCallback((rate: number) => {
    if (rate > 0) rateRef.current = rate;
  }, []);

  const schedule = useCallback((pcm16: Int16Array) => {
    try {
      const ctx = (ctxRef.current ??= new AudioContext());
      const f32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) f32[i] = pcm16[i] / 32768;
      const buffer = ctx.createBuffer(1, f32.length, rateRef.current);
      buffer.copyToChannel(f32, 0);

      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(ctx.destination);
      scheduledRef.current.add(src);
      src.onended = () => scheduledRef.current.delete(src);

      const startAt = Math.max(ctx.currentTime, nextStartRef.current);
      src.start(startAt);
      nextStartRef.current = startAt + buffer.duration;
    } catch {
      // best-effort playback; ignore decode / audio-context errors
    }
  }, []);

  const pushChunk = useCallback(
    (base64Pcm: string | undefined) => {
      if (!base64Pcm) return;
      try {
        const binary = atob(base64Pcm);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        schedule(new Int16Array(bytes.buffer));
      } catch {
        // best-effort playback; ignore malformed base64
      }
    },
    [schedule],
  );

  const pushPcm = useCallback(
    (pcm: ArrayBuffer) => schedule(new Int16Array(pcm)),
    [schedule],
  );

  /** Stop everything already queued — the agent must go silent immediately. */
  const flush = useCallback(() => {
    for (const src of scheduledRef.current) {
      try {
        src.stop();
      } catch {
        // already finished
      }
    }
    scheduledRef.current.clear();
    nextStartRef.current = 0;
  }, []);

  const reset = flush;

  useEffect(
    () => () => {
      flush();
      void ctxRef.current?.close();
      ctxRef.current = null;
    },
    [flush],
  );

  // Stable identity: callers put this object in effect dependency arrays, and a
  // fresh literal every render would re-run their cleanups mid-session.
  return useMemo(
    () => ({ pushChunk, pushPcm, flush, reset, setSampleRate }),
    [pushChunk, pushPcm, flush, reset, setSampleRate],
  );
};
