import { useTranslation } from "react-i18next";

import { cn } from "@/shared/lib/utils";

import { TIMING_STAGES } from "../lib/format";
import type { VoiceSessionDetail, VoiceTurnTimings } from "../model/types";

interface TurnTimingsProps {
  timings: VoiceTurnTimings;
  className?: string;
}

/** One cascade turn's stage breakdown on a single line; renders nothing without stages. */
export const TurnTimings = ({ timings, className }: TurnTimingsProps) => {
  const { t } = useTranslation();
  const stages = TIMING_STAGES.filter(
    (stage) => timings[stage] != null && (stage !== "llmOverlapMs" || timings.speculative)
  );
  if (stages.length === 0) return null;

  return (
    <p
      className={cn(
        "flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] tabular-nums text-muted-foreground",
        className
      )}
    >
      {stages.map((stage) => (
        <span key={stage} className={stage === "totalMs" ? "text-foreground" : undefined}>
          {t(`voiceSessions.stages.${stage}`)}{" "}
          {t("voiceSessions.detail.ms", { ms: timings[stage] })}
        </span>
      ))}
      {timings.smartTurnAsks != null && timings.smartTurnAsks > 0 && (
        <span>
          {t("voiceSessions.detail.smartTurn", {
            prob: timings.smartTurnProb?.toFixed(2) ?? "—",
            count: timings.smartTurnAsks,
          })}
        </span>
      )}
      {timings.speculative && <span>{t("voiceSessions.detail.speculative")}</span>}
    </p>
  );
};

interface TimingSummaryProps {
  summary: NonNullable<VoiceSessionDetail["timingSummary"]>;
}

/** p50 / p95 per cascade stage across a call. */
export const TimingSummary = ({ summary }: TimingSummaryProps) => {
  const { t } = useTranslation();
  const stages = TIMING_STAGES.filter((stage) => summary[stage]);
  if (stages.length === 0) return null;

  return (
    <table className="w-full text-xs tabular-nums">
      <thead className="text-muted-foreground">
        <tr>
          <th className="py-1 text-left font-normal">{t("voiceSessions.detail.stage")}</th>
          <th className="py-1 text-right font-normal">p50</th>
          <th className="py-1 text-right font-normal">p95</th>
        </tr>
      </thead>
      <tbody>
        {stages.map((stage) => (
          <tr key={stage} className="border-t border-border">
            <td className="py-1.5">{t(`voiceSessions.stages.${stage}`)}</td>
            <td className="py-1.5 text-right">
              {t("voiceSessions.detail.ms", { ms: summary[stage]!.p50 })}
            </td>
            <td className="py-1.5 text-right">
              {t("voiceSessions.detail.ms", { ms: summary[stage]!.p95 })}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};
