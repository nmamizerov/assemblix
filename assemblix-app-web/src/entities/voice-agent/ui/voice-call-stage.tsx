import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Mic, Square } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/shared/lib/utils";

import type { useVoiceCall } from "../lib/use-voice-call";
import { VoiceOrb } from "./voice-orb";

interface VoiceCallStageProps {
  call: ReturnType<typeof useVoiceCall>;
}

// Above this the round trip is worth pointing at rather than celebrating. The
// thresholds are the ones the feature is judged on, so they are stated plainly.
const LATENCY_GOOD_MS = 800;
const LATENCY_FAIR_MS = 1500;

export const VoiceCallStage = ({ call }: VoiceCallStageProps) => {
  const { t } = useTranslation();
  const { status, transcript, interim, firstAudioMs, error, levels } = call;
  const isLive = status === "live";
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [transcript, interim]);

  const stateKey =
    status === "connecting"
      ? "connecting"
      : status === "ending"
        ? "ending"
        : isLive
          ? "live"
          : "idle";

  return (
    <section className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex items-center justify-between gap-3 px-5 pt-5 pb-1">
        <h2 className="text-sm font-medium tracking-tight text-foreground">
          {t("voiceAgents.testCall.title")}
        </h2>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-xs tabular-nums transition-colors",
            isLive ? "text-primary" : "text-muted-foreground",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full transition-colors",
              isLive ? "bg-primary" : "bg-muted-foreground/40",
            )}
          />
          {t(`voiceAgents.testCall.state.${stateKey}`)}
        </span>
      </header>

      <div className="flex flex-col items-center px-5 pt-2">
        <div className="relative aspect-square w-full max-w-[236px]">
          <VoiceOrb status={status} levels={levels} />
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <AnimatePresence mode="wait">
              <motion.span
                key={stateKey}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="text-xs text-muted-foreground"
              >
                {isLive ? t("voiceAgents.testCall.speakNow") : null}
              </motion.span>
            </AnimatePresence>
          </div>
        </div>

        <button
          type="button"
          onClick={status === "idle" ? call.start : call.stop}
          disabled={status === "connecting" || status === "ending"}
          className={cn(
            "mt-4 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium",
            "transition-[background-color,color,opacity] duration-200",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card",
            "disabled:opacity-60",
            isLive
              ? "bg-foreground text-background hover:bg-foreground/90"
              : "bg-primary text-primary-foreground hover:bg-primary/90",
          )}
        >
          {isLive ? (
            <Square className="h-3.5 w-3.5 fill-current" />
          ) : (
            <Mic className="h-4 w-4" />
          )}
          {isLive
            ? t("voiceAgents.testCall.hangUp")
            : t("voiceAgents.testCall.callButton")}
        </button>

        <div className="mt-2.5 h-4 text-xs">
          {error ? (
            <span className="text-destructive">
              {t(`voiceAgents.testCall.errors.${error}`)}
            </span>
          ) : firstAudioMs !== null ? (
            <span
              className={cn(
                "tabular-nums",
                firstAudioMs <= LATENCY_GOOD_MS
                  ? "text-primary"
                  : firstAudioMs <= LATENCY_FAIR_MS
                    ? "text-muted-foreground"
                    : "text-destructive",
              )}
            >
              {t("voiceAgents.testCall.firstAudio", { ms: firstAudioMs })}
            </span>
          ) : null}
        </div>
      </div>

      <div
        ref={scrollRef}
        className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto border-t border-border px-5 py-4"
      >
        {transcript.length === 0 && !interim ? (
          <p className="max-w-[34ch] text-xs leading-relaxed text-muted-foreground">
            {status === "idle"
              ? t("voiceAgents.testCall.hintIdle")
              : t("voiceAgents.testCall.hintLive")}
          </p>
        ) : (
          <>
            {transcript.map((line, index) => (
              <Line key={index} role={line.role} text={line.text} />
            ))}
            {interim && <Line role={interim.role} text={interim.text} pending />}
          </>
        )}
      </div>
    </section>
  );
};

interface LineProps {
  role: "user" | "assistant";
  text: string;
  pending?: boolean;
}

const Line = ({ role, text, pending }: LineProps) => {
  const { t } = useTranslation();
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
      className="grid grid-cols-[auto_1fr] gap-x-2.5"
    >
      <span
        className={cn(
          "mt-px text-[11px] leading-5 tracking-wide uppercase",
          role === "assistant" ? "text-primary" : "text-muted-foreground",
        )}
      >
        {role === "assistant"
          ? t("voiceAgents.testCall.agent")
          : t("voiceAgents.testCall.you")}
      </span>
      <p
        className={cn(
          "text-sm leading-5 text-foreground",
          pending && "text-muted-foreground",
        )}
      >
        {text}
      </p>
    </motion.div>
  );
};
