import { Loader2, PhoneOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatCredits, formatDuration } from "../lib/format";
import type { VoiceSession } from "../model/types";

interface VoiceSessionListProps {
  sessions: VoiceSession[];
  isLoading: boolean;
  isError: boolean;
  onOpen: (sessionId: string) => void;
}

const outcomeTone = (session: VoiceSession): string =>
  session.status === "failed"
    ? "text-destructive"
    : session.status === "active"
      ? "text-primary"
      : "text-muted-foreground";

export const VoiceSessionList = ({
  sessions,
  isLoading,
  isError,
  onOpen,
}: VoiceSessionListProps) => {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  if (isError) {
    return (
      <p className="py-10 text-center text-sm text-destructive">
        {t("voiceSessions.loadError")}
      </p>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <PhoneOff className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">{t("voiceSessions.empty")}</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          {t("voiceSessions.emptyDescription")}
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 text-left font-medium">
              {t("voiceSessions.columns.startedAt")}
            </th>
            <th className="px-4 py-2.5 text-right font-medium">
              {t("voiceSessions.columns.duration")}
            </th>
            <th className="px-4 py-2.5 text-right font-medium">
              {t("voiceSessions.columns.turns")}
            </th>
            <th className="px-4 py-2.5 text-right font-medium">
              {t("voiceSessions.columns.cost")}
            </th>
            <th className="px-4 py-2.5 text-left font-medium">
              {t("voiceSessions.columns.outcome")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr
              key={session.id}
              onClick={() => onOpen(session.id)}
              className="cursor-pointer border-t border-border transition-colors hover:bg-muted/40"
            >
              <td className="px-4 py-3">
                {new Date(session.startedAt).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatDuration(session.durationSec)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {session.turnCount}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCredits(session.totalCredits)}
              </td>
              <td className={`px-4 py-3 ${outcomeTone(session)}`}>
                {session.endReason
                  ? t(`voiceSessions.endReason.${session.endReason}`, {
                      defaultValue: session.endReason,
                    })
                  : t(`voiceSessions.status.${session.status}`)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
