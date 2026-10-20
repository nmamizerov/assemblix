import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatUsd } from "@/shared/lib/format-cost";
import { cn } from "@/shared/lib/utils";

import type { VoiceLlmCall, VoiceTurnUsage } from "../model/types";

interface TurnCostChipsProps {
  usage: VoiceTurnUsage;
  className?: string;
}

const Chip = ({ label, value, title }: { label: string; value: string; title?: string }) => (
  <span
    title={title}
    className="rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-[11px] tabular-nums text-muted-foreground"
  >
    {label} <span className="text-foreground">{value}</span>
  </span>
);

/** Per-turn spend by cascade stage. */
export const TurnCostChips = ({ usage, className }: TurnCostChipsProps) => {
  const { t } = useTranslation();

  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {usage.sttCostUsdEstimate != null && (
        <Chip
          label={t("voiceSessions.llm.chipStt")}
          value={`≈${formatUsd(usage.sttCostUsdEstimate)}`}
          title={t("voiceSessions.llm.sttEstimateHint", {
            seconds: (usage.sttSeconds ?? 0).toFixed(1),
          })}
        />
      )}
      {usage.llmCostUsd != null && (
        <Chip label={t("voiceSessions.llm.chipLlm")} value={formatUsd(usage.llmCostUsd)} />
      )}
      {usage.ttsCostUsd != null && (
        <Chip
          label={t("voiceSessions.llm.chipTts")}
          value={formatUsd(usage.ttsCostUsd)}
          title={t("voiceSessions.llm.ttsCharsHint", { chars: usage.ttsChars ?? 0 })}
        />
      )}
    </div>
  );
};

const Stat = ({ label, value }: { label: string; value: string }) => (
  <div>
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="tabular-nums">{value}</dd>
  </div>
);

interface LlmCallPanelProps {
  call: VoiceLlmCall;
  className?: string;
}

/** Collapsed by default: what a cascade turn sent to the LLM and what came back. */
export const LlmCallPanel = ({ call, className }: LlmCallPanelProps) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const failed = call.outcome !== "ok";
  const ms = (value: number | null) =>
    value == null ? "—" : t("voiceSessions.detail.ms", { ms: value });
  const params = Object.entries(call.params ?? {});

  return (
    <div className={cn("rounded-md border border-border", className)}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0" />
        )}
        <span>{t("voiceSessions.llm.title")}</span>
        <span className="truncate font-normal tabular-nums">
          {call.model} · {ms(call.ttftMs)} · {formatUsd(call.costUsd)}
        </span>
        {failed && (
          <span className="ml-auto shrink-0 rounded bg-destructive/10 px-1.5 py-0.5 text-[11px] text-destructive">
            {t(`voiceSessions.llm.outcome.${call.outcome}`, { defaultValue: call.outcome })}
          </span>
        )}
      </button>

      {open && (
        <div className="space-y-3 border-t border-border px-3 py-3 text-xs">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
            <Stat
              label={t("voiceSessions.llm.model")}
              value={[call.provider, call.model].filter(Boolean).join(" / ")}
            />
            {call.effectiveModel && call.effectiveModel !== call.model && (
              <Stat label={t("voiceSessions.llm.effectiveModel")} value={call.effectiveModel} />
            )}
            <Stat
              label={t("voiceSessions.llm.tokens")}
              value={t("voiceSessions.detail.tokens", {
                input: call.inputTokens,
                output: call.outputTokens,
              })}
            />
            {call.cachedInputTokens != null && (
              <Stat label={t("voiceSessions.llm.cached")} value={String(call.cachedInputTokens)} />
            )}
            <Stat label={t("voiceSessions.llm.cost")} value={formatUsd(call.costUsd)} />
            <Stat label={t("voiceSessions.llm.ttft")} value={ms(call.ttftMs)} />
            <Stat label={t("voiceSessions.llm.duration")} value={ms(call.durationMs)} />
            <Stat
              label={t("voiceSessions.llm.outcomeLabel")}
              value={t(`voiceSessions.llm.outcome.${call.outcome}`, {
                defaultValue: call.outcome,
              })}
            />
          </dl>

          {params.length > 0 && (
            <div>
              <p className="mb-1 text-muted-foreground">{t("voiceSessions.llm.params")}</p>
              <p className="flex flex-wrap gap-1.5 font-mono text-[11px]">
                {params.map(([key, value]) => (
                  <span key={key} className="rounded bg-muted px-1.5 py-0.5">
                    {key}={JSON.stringify(value)}
                  </span>
                ))}
              </p>
            </div>
          )}

          {call.error && (
            <p className="whitespace-pre-wrap rounded bg-destructive/10 px-2 py-1.5 text-destructive">
              {call.error}
            </p>
          )}

          <div>
            <p className="mb-1 text-muted-foreground">
              {t("voiceSessions.llm.messages", { count: call.messages.length })}
            </p>
            <ol className="max-h-80 space-y-1.5 overflow-y-auto rounded border border-border bg-muted/20 p-2">
              <li className="italic text-muted-foreground">
                {t("voiceSessions.llm.systemRef")}
              </li>
              {call.messages.map((message, index) => (
                <li key={index} className="rounded bg-background px-2 py-1.5">
                  <span className="mr-1.5 font-medium uppercase tracking-wide text-muted-foreground">
                    {message.role === "user"
                      ? t("voiceSessions.llm.roleUser")
                      : t("voiceSessions.llm.roleAssistant")}
                  </span>
                  <span className="whitespace-pre-wrap break-words">{message.content}</span>
                </li>
              ))}
            </ol>
          </div>

          <div>
            <p className="mb-1 text-muted-foreground">{t("voiceSessions.llm.response")}</p>
            <p className="max-h-60 overflow-y-auto whitespace-pre-wrap break-words rounded border border-border bg-muted/20 p-2">
              {call.response || "—"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
