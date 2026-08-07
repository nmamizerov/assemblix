import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  formatCredits,
  formatDuration,
  useGetVoiceSessionQuery,
} from "@/entities/voice-session";
import type { VoiceSessionExecution } from "@/entities/voice-session";
import { Button } from "@/shared/ui/button";

export const VoiceSessionDetailsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projectId, sessionId } = useParams();

  const {
    data: session,
    isLoading,
    isError,
  } = useGetVoiceSessionQuery(sessionId!, { skip: !sessionId });

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (isError || !session) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-4 text-center">
        <div className="rounded-full bg-destructive/10 p-4">
          <AlertCircle className="h-10 w-10 text-destructive" />
        </div>
        <p className="text-xl font-semibold tracking-tight">
          {t("voiceSessions.detail.loadError")}
        </p>
      </div>
    );
  }

  const openExecution = (execution: VoiceSessionExecution) =>
    navigate(
      `/projects/${projectId}/workflows/${execution.workflowId}/executions/${execution.id}`
    );

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2 text-muted-foreground"
          onClick={() =>
            navigate(
              `/projects/${projectId}/voice-agents/${session.voiceAgentId}`
            )
          }
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t("voiceSessions.detail.back")}
        </Button>

        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("voiceSessions.detail.title")}
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            {new Date(session.startedAt).toLocaleString()}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="tabular-nums">
              {formatDuration(session.durationSec)}
            </span>
            <span aria-hidden>·</span>
            <span className="tabular-nums">
              {formatCredits(session.totalCredits)}
            </span>
            <span aria-hidden>·</span>
            <span>
              {session.endReason
                ? t(`voiceSessions.endReason.${session.endReason}`, {
                    defaultValue: session.endReason,
                  })
                : t(`voiceSessions.status.${session.status}`)}
            </span>
            <span aria-hidden>·</span>
            <span className="tabular-nums">
              {t("voiceSessions.detail.tokens", {
                input: session.inputTokens,
                output: session.outputTokens,
              })}
            </span>
          </div>
        </div>
      </header>

      <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="space-y-3">
          <h2 className="text-sm font-medium">
            {t("voiceSessions.detail.transcript")}
          </h2>
          {session.transcript.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              {t("voiceSessions.detail.emptyTranscript")}
            </p>
          ) : (
            <ol className="space-y-2">
              {session.transcript.map((line, index) => (
                <li
                  key={index}
                  className="rounded-lg border border-border px-4 py-3"
                >
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    {line.role === "user"
                      ? t("voiceSessions.detail.you")
                      : t("voiceSessions.detail.agent")}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{line.text}</p>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium">
            {t("voiceSessions.detail.executions")}
          </h2>
          {session.executions.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              {t("voiceSessions.detail.noExecutions")}
            </p>
          ) : (
            <ul className="space-y-2">
              {session.executions.map((execution) => (
                <li key={execution.id}>
                  <button
                    type="button"
                    onClick={() => openExecution(execution)}
                    className="w-full rounded-lg border border-border px-4 py-3 text-left transition-colors hover:bg-muted/40"
                  >
                    <p className="text-sm font-medium">{execution.status}</p>
                    <p className="mt-1 text-xs text-muted-foreground tabular-nums">
                      {execution.startedAt
                        ? new Date(execution.startedAt).toLocaleTimeString()
                        : "—"}
                      {" · "}
                      {formatCredits(execution.totalCredits)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
};
