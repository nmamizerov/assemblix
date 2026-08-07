import { useEffect, useRef } from "react";

import type { CallLevels, CallStatus } from "../lib/use-voice-call";

interface VoiceOrbProps {
  status: CallStatus;
  levels: React.RefObject<CallLevels>;
}

const RAYS = 72;
// How fast a ray falls back once the sound stops. Attack is instant so speech
// reads as immediate; release is slow so the shape settles instead of flickering.
const RELEASE = 0.12;
const IDLE_BREATH = 0.035;

const readToken = (styles: CSSStyleDeclaration, name: string, fallback: string) =>
  styles.getPropertyValue(name).trim() || fallback;

/**
 * The call's living surface: a ring of rays whose length is the actual loudness
 * of whoever is speaking, sampled from the PCM frames themselves.
 *
 * Indigo is the agent's voice — the accent is spent on the thing the page exists
 * to evaluate. The caller's own voice is drawn in ink, present but not competing.
 */
export const VoiceOrb = ({ status, levels }: VoiceOrbProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // The animation loop reads status without being restarted by it.
  const statusRef = useRef(status);
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const rays = new Float32Array(RAYS);
    let frame = 0;
    let raf = 0;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    const draw = () => {
      const { width, height } = canvas.getBoundingClientRect();
      const cx = width / 2;
      const cy = height / 2;
      const unit = Math.min(width, height);
      ctx.clearRect(0, 0, width, height);

      const styles = getComputedStyle(canvas);
      const accent = readToken(styles, "--primary", "#6366f1");
      const ink = readToken(styles, "--foreground", "#09090b");
      const hairline = readToken(styles, "--border", "#e4e4e7");

      const live = statusRef.current === "live";
      const { user, agent } = levels.current;
      // Whoever is louder owns the colour; ties and silence fall back to ink.
      const agentLeads = agent >= user;
      const loudest = Math.max(user, agent);
      const colour = loudest < 0.02 ? ink : agentLeads ? accent : ink;

      frame += 1;
      const breath = reduced ? 0 : Math.sin(frame / 45) * IDLE_BREATH;
      const core = unit * 0.17;
      const base = unit * 0.23;

      // Resting ring — the stage is visibly present before anything is said.
      ctx.beginPath();
      ctx.arc(cx, cy, base + unit * 0.14, 0, Math.PI * 2);
      ctx.strokeStyle = hairline;
      ctx.lineWidth = 1;
      ctx.stroke();

      for (let i = 0; i < RAYS; i++) {
        // Each ray leans on a different slice of the waveform so the ring reads
        // as a voice rather than a uniformly pulsing circle.
        const phase = reduced ? 0.5 : (Math.sin(frame / 22 + i * 0.7) + 1) / 2;
        const target = live
          ? loudest * (0.45 + 0.55 * phase) + Math.abs(breath)
          : Math.max(0, breath);
        rays[i] += (target - rays[i]) * (target > rays[i] ? 1 : RELEASE);

        const length = unit * 0.02 + rays[i] * unit * 0.2;
        const angle = (i / RAYS) * Math.PI * 2 - Math.PI / 2;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);

        ctx.beginPath();
        ctx.moveTo(cx + cos * base, cy + sin * base);
        ctx.lineTo(cx + cos * (base + length), cy + sin * (base + length));
        ctx.strokeStyle = colour;
        ctx.globalAlpha = 0.2 + Math.min(0.7, rays[i] * 2.2);
        ctx.lineWidth = unit * 0.006;
        ctx.lineCap = "round";
        ctx.stroke();
      }

      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, core * (1 + loudest * 0.08), 0, Math.PI * 2);
      ctx.fillStyle = colour;
      ctx.globalAlpha = live ? 0.1 : 0.05;
      ctx.fill();
      ctx.globalAlpha = 1;

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [levels]);

  return <canvas ref={canvasRef} className="h-full w-full" aria-hidden />;
};
