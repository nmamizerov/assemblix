import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { toast } from "sonner";
import { Panel, useNodes } from "@xyflow/react";
import { motion } from "framer-motion";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Switch } from "@/shared/ui/switch";
import { Label } from "@/shared/ui/label";
import { Play, Square, AlertCircle, Trash2, MessageCircle, Mic } from "lucide-react";
import { useWorkflowDebug } from "../../lib/use-workflow-debug";
import { useVoiceRecorder } from "../../lib/use-voice-recorder";
import { useAvatarSession } from "../../lib/use-avatar-session";
import { ExecutionViewer } from "./execution-viewer";
import {
  NodeType,
  type StartNodeConfig,
  type Workflow,
} from "@/entities/workflow/model/types";
import { cn } from "@/shared/lib/utils";
import { selectCurrentProjectId } from "@/entities/organization";

interface DebugPanelProps {
  workflow: Workflow;
}

export const DebugPanel = ({ workflow }: DebugPanelProps) => {
  const { t } = useTranslation();
  const [inputMessage, setInputMessage] = useState("");
  const [streaming, setStreaming] = useState(false);
  const currentProjectId = useSelector(selectCurrentProjectId);

  // Avatar mode: the workflow has a configured AI-avatar persona (set from the
  // editor header). Renders a live talking-head video wired to the streaming run.
  const hasAvatar = Boolean(workflow.config?.avatar);
  const avatarSession = useAvatarSession(workflow.id);

  const {
    history,
    isRunning,
    error,
    isSessionClosed,
    startDebugExecution,
    startDebugAudioExecution,
    stopExecution,
    clearSession,
    continueSession,
  } = useWorkflowDebug({
    workflow,
    projectId: currentProjectId || undefined,
    onStreamDelta: hasAvatar ? avatarSession.onDelta : undefined,
    onAvatarNodeComplete: hasAvatar
      ? avatarSession.onAvatarNodeComplete
      : undefined,
  });
  const recorder = useVoiceRecorder();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Mint + connect the avatar renderer for the lifetime of avatar mode.
  useEffect(() => {
    if (!hasAvatar) return;
    avatarSession.connect();
    return () => avatarSession.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAvatar, workflow.id]);

  // Voice input is available only when the workflow's START node accepts it.
  // Read from the live ReactFlow nodes (not the persisted `workflow` prop) so a
  // freshly toggled "accept voice" reflects immediately, without a page reload.
  const nodes = useNodes();
  const startNode = nodes.find((node) => node.type === NodeType.START);
  const acceptVoice = Boolean(
    (startNode?.data as StartNodeConfig | undefined)?.acceptVoice,
  );

  const handleMicToggle = async () => {
    if (isRunning) return;
    if (recorder.isRecording) {
      const audio = await recorder.stop();
      if (audio) {
        startDebugAudioExecution(workflow.id, audio.blob, audio.filename);
      } else {
        // Empty recording — the mic captured nothing.
        toast.error(t("debug.noAudioRecorded"));
      }
    } else {
      await recorder.start();
    }
  };

  // Surface microphone access / recording failures.
  useEffect(() => {
    if (recorder.error) {
      toast.error(t("debug.micError", { error: recorder.error }));
    }
  }, [recorder.error, t]);

  // Автоскролл к последнему событию
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  const handleExecute = () => {
    if (!inputMessage.trim() || isRunning) return;
    startDebugExecution(workflow.id, inputMessage, streaming);
    setInputMessage("");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleExecute();
    }
  };

  return (
    <Panel
      position="top-right"
      className="mt-20! w-[400px] bg-panel rounded-xl overflow-hidden flex flex-col h-[calc(100vh-10rem)]"
    >
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className="flex flex-col flex-1 h-full"
      >
        {/* Заголовок */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">{t("debug.title")}</h3>
            {isRunning && (
              <div className="flex items-center gap-1.5">
                <div className="size-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs text-muted-foreground">
                  {t("debug.running")}
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={clearSession}
              title={t("debug.clearHistory")}
            >
              <Trash2 className="size-3.5 text-muted-foreground" />
            </Button>
          </div>
        </div>

        {/* Аватар: рендерится, когда у workflow настроена AI-avatar персона */}
        {hasAvatar && (
          <div className="px-4 pt-4 shrink-0">
            <video
              ref={avatarSession.videoRef}
              autoPlay
              playsInline
              className="w-full aspect-video rounded-lg bg-black object-cover"
            />
          </div>
        )}

        {/* Список сообщений чата */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ScrollArea className="h-full">
            <div ref={scrollRef} className="p-4 space-y-6">
              {history.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground text-sm">
                  <p className="mb-2">{t("debug.noMessages")}</p>
                  <p className="text-xs">{t("debug.noMessagesHelp")}</p>
                </div>
              ) : (
                <>
                  {history.map((item) => (
                    <div
                      key={item.id}
                      className={cn(
                        "flex flex-col gap-2",
                        item.type === "user" ? "items-end" : "items-start",
                      )}
                    >
                      {item.type === "user" ? (
                        item.audioUrl ? (
                          <audio
                            controls
                            src={item.audioUrl}
                            className="max-w-[85%] h-9"
                          />
                        ) : (
                          <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-4 py-2 text-primary-foreground text-sm">
                            {item.content}
                          </div>
                        )
                      ) : (
                        <div className="w-full space-y-2">
                          {/* Индикатор бота */}
                          <div className="flex items-center gap-2 text-xs text-muted-foreground font-medium">
                            {t("workflow.nodes.agent")}
                          </div>

                          {/* Лог выполнения (шаги) */}
                          <div className="ml-2 pl-4 border-l-2 border-border/50">
                            <ExecutionViewer
                              events={item.events || []}
                              isRunning={
                                isRunning &&
                                item === history[history.length - 1]
                              }
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Ошибка */}
        {error && (
          <div className="mx-4 mb-4">
            <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg max-h-[200px] overflow-y-auto">
              <AlertCircle className="size-4 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-red-900 dark:text-red-100">
                  {t("executionViewer.errorExecution")}
                </p>
                <p className="text-xs wrap-break-word text-red-700 dark:text-red-300 mt-1">
                  {error}
                </p>
              </div>
            </div>
          </div>
        )}
        {/* Поле ввода внизу (как в чате) или блок закрытой сессии */}
        {isSessionClosed ? (
          <div className="p-4 border-t border-border bg-background/50">
            <div className="flex flex-col gap-3">
              <div className="flex items-start gap-2 p-3 bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-800 rounded-lg">
                <MessageCircle className="size-4 text-orange-600 dark:text-orange-400 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-orange-900 dark:text-orange-100">
                    {t("debug.sessionClosed")}
                  </p>
                  <p className="text-xs text-orange-700 dark:text-orange-300 mt-1">
                    {t("debug.sessionClosedDesc")}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={continueSession}
                  className="flex-1"
                  size="sm"
                  variant="outline"
                >
                  {t("debug.continueSession")}
                </Button>
                <Button onClick={clearSession} className="flex-1" size="sm">
                  {t("debug.startNewSession")}
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 border-t border-border bg-background/50">
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Input
                  placeholder={
                    recorder.isRecording
                      ? t("debug.recording")
                      : t("debug.inputPlaceholder")
                  }
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={handleKeyPress}
                  disabled={isRunning || recorder.isRecording}
                  className="text-sm flex-1"
                />
                {acceptVoice && (
                  <Button
                    type="button"
                    variant={recorder.isRecording ? "destructive" : "ghost"}
                    size="icon"
                    onClick={handleMicToggle}
                    disabled={isRunning}
                    title={
                      recorder.isRecording
                        ? t("debug.stopRecording")
                        : t("debug.recordVoice")
                    }
                    className={cn(recorder.isRecording && "animate-pulse")}
                  >
                    <Mic className="size-4" />
                  </Button>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="debug-streaming"
                  checked={streaming}
                  onCheckedChange={setStreaming}
                  disabled={isRunning}
                  showIcons={false}
                />
                <Label
                  htmlFor="debug-streaming"
                  className="text-xs text-muted-foreground cursor-pointer"
                  title={t("debug.streamingHint")}
                >
                  {t("debug.streaming")}
                </Label>
              </div>
              <div className="flex gap-2">
                {!isRunning ? (
                  <Button
                    onClick={handleExecute}
                    disabled={!inputMessage.trim()}
                    className="flex-1"
                    size="sm"
                  >
                    <Play className="size-4 mr-2" />
                    {t("debug.execute")}
                  </Button>
                ) : (
                  <Button
                    onClick={stopExecution}
                    variant="destructive"
                    className="flex-1"
                    size="sm"
                  >
                    <Square className="size-4 mr-2" />
                    {t("debug.stop")}
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </motion.div>
    </Panel>
  );
};
