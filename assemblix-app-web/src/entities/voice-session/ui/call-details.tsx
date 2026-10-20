import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatUsd } from "@/shared/lib/format-cost";

import { formatCredits } from "../lib/format";
import type { VoiceCallDetails } from "../model/types";

interface CallInstructionsProps {
  details: VoiceCallDetails;
}

/** The system instructions every LLM call of the call was sent with, shown once. */
export const CallInstructions = ({ details }: CallInstructionsProps) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const brain = details.brain;
  const params = Object.entries(brain?.params ?? {});

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-1.5 px-4 py-3 text-left text-sm font-medium"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        {t("voiceSessions.llm.instructions")}
        {brain && (
          <span className="truncate text-xs font-normal text-muted-foreground">
            {[brain.provider, brain.model].filter(Boolean).join(" / ")}
            {brain.historyTurns != null &&
              ` · ${t("voiceSessions.llm.historyTurns", { count: brain.historyTurns })}`}
          </span>
        )}
      </button>
      {open && (
        <div className="space-y-2 border-t border-border px-4 py-3 text-xs">
          {params.length > 0 && (
            <p className="flex flex-wrap gap-1.5 font-mono text-[11px]">
              {params.map(([key, value]) => (
                <span key={key} className="rounded bg-muted px-1.5 py-0.5">
                  {key}={JSON.stringify(value)}
                </span>
              ))}
            </p>
          )}
          <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap break-words rounded border border-border bg-muted/20 p-2 font-sans">
            {details.instructions || "—"}
          </pre>
        </div>
      )}
    </div>
  );
};

interface StageCostBreakdownProps {
  details: VoiceCallDetails;
}

/** Whole-call spend per cascade stage, as billed. */
export const StageCostBreakdown = ({ details }: StageCostBreakdownProps) => {
  const { t } = useTranslation();
  const costs = details.costs;
  if (!costs) return null;

  const stages = [
    {
      key: "stt",
      label: t("voiceSessions.llm.chipStt"),
      model: details.stt?.model,
      usd: costs.sttCostUsd,
      amount:
        costs.sttSeconds != null
          ? t("voiceSessions.llm.seconds", { seconds: costs.sttSeconds.toFixed(1) })
          : null,
    },
    {
      key: "llm",
      label: t("voiceSessions.llm.chipLlm"),
      model: details.brain?.model,
      usd: costs.llmCostUsd,
      amount: null,
    },
    {
      key: "tts",
      label: t("voiceSessions.llm.chipTts"),
      model: details.tts?.model,
      usd: costs.ttsCostUsd,
      amount:
        costs.ttsChars != null ? t("voiceSessions.llm.chars", { chars: costs.ttsChars }) : null,
    },
  ];
  const providerTotal = stages.reduce((sum, stage) => sum + (stage.usd ?? 0), 0);

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {stages.map((stage) => (
        <div key={stage.key} className="rounded-lg border border-border px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {stage.label}
          </p>
          <p className="mt-0.5 text-sm font-medium tabular-nums">{formatUsd(stage.usd ?? 0)}</p>
          <p className="truncate text-[11px] text-muted-foreground tabular-nums">
            {[stage.model, stage.amount].filter(Boolean).join(" · ") || "—"}
          </p>
        </div>
      ))}
      <div className="rounded-lg border border-border px-3 py-2">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
          {t("voiceSessions.llm.providersTotal")}
        </p>
        <p className="mt-0.5 text-sm font-medium tabular-nums">{formatUsd(providerTotal)}</p>
      </div>
      <div className="rounded-lg border border-border px-3 py-2">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
          {t("voiceSessions.llm.platformFee")}
        </p>
        <p className="mt-0.5 text-sm font-medium tabular-nums">
          {formatCredits(costs.platformFeeCredits ?? 0)}
        </p>
        <p className="truncate text-[11px] text-muted-foreground tabular-nums">
          {t("voiceSessions.llm.marginCredits", {
            credits: formatCredits(costs.providerMarginCredits ?? 0),
          })}
        </p>
      </div>
    </div>
  );
};
