import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Label } from "@/shared/ui/label";
import { ExecutionsList } from "@/entities/execution";
import { ChatSessionsList, ChatDetailPanel } from "@/entities/chat-session";
import { ExecutionViewerContent } from "@/entities/execution";
import { cn } from "@/shared/lib/utils";

interface AgentCallsDialogProps {
  workflowId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type ViewMode = { type: "list" } | { type: "execution"; executionId: string };

export const AgentCallsDialog = ({
  workflowId,
  open,
  onOpenChange,
}: AgentCallsDialogProps) => {
  const { t } = useTranslation();
  const [includeDebug, setIncludeDebug] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>({ type: "list" });
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"executions" | "chats">(
    "executions",
  );

  const handleExecutionClick = (executionId: string) => {
    setViewMode({ type: "execution", executionId });
  };

  const handleBackToList = () => {
    setViewMode({ type: "list" });
  };

  const handleChatClick = (chatId: string) => {
    setSelectedChatId(chatId);
  };

  const handleExecutionClickFromChat = (executionId: string) => {
    setViewMode({ type: "execution", executionId });
  };

  // Сброс состояния при закрытии модалки
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setViewMode({ type: "list" });
      setSelectedChatId(null);
      setActiveTab("executions");
    }
    onOpenChange(newOpen);
  };

  const isExecutionMode = viewMode.type === "execution";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className={cn(
          "overflow-hidden flex flex-col",
          isExecutionMode
            ? "max-w-[95vw] w-[95vw] max-h-[90vh] h-[90vh]"
            : "max-w-5xl max-h-[80vh] h-[80vh]",
        )}
      >
        {isExecutionMode ? (
          // Режим просмотра execution
          <ExecutionViewerContent
            executionId={viewMode.executionId}
            onBack={handleBackToList}
          />
        ) : (
          // Режим списка
          <>
            <DialogHeader>
              <DialogTitle>{t("workflow.agentCalls.title")}</DialogTitle>
            </DialogHeader>
            <Tabs
              value={activeTab}
              onValueChange={(value) =>
                setActiveTab(value as "executions" | "chats")
              }
              className="flex-1 flex flex-col overflow-hidden min-h-0"
            >
              <div className="space-y-4">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="executions">
                    {t("workflow.agentCalls.executions")}
                  </TabsTrigger>
                  <TabsTrigger value="chats">
                    {t("workflow.agentCalls.chats")}
                  </TabsTrigger>
                </TabsList>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="includeDebugModal"
                    checked={includeDebug}
                    onChange={(e) => setIncludeDebug(e.target.checked)}
                    className="h-4 w-4 rounded border-border text-primary focus:ring-2 focus:ring-primary"
                  />
                  <Label
                    htmlFor="includeDebugModal"
                    className="cursor-pointer text-sm"
                  >
                    {t("sessions.showTestSessions")}
                  </Label>
                </div>
              </div>

              <TabsContent
                value="executions"
                className="flex-1 overflow-auto mt-4 min-h-0"
              >
                <ExecutionsList
                  workflowId={workflowId}
                  includeDebug={includeDebug}
                  onItemClick={handleExecutionClick}
                />
              </TabsContent>

              <TabsContent
                value="chats"
                className="flex-1 overflow-hidden mt-4 min-h-0"
              >
                <div className="flex gap-4 h-full min-h-0">
                  {/* Список чатов */}
                  <div className="w-2/5 overflow-auto min-h-0">
                    <ChatSessionsList
                      workflowId={workflowId}
                      includeDebug={includeDebug}
                      onItemClick={handleChatClick}
                      selectedId={selectedChatId || undefined}
                    />
                  </div>

                  {/* Детали чата */}
                  <div className="flex-1 border-l border-border overflow-hidden min-h-0">
                    {selectedChatId ? (
                      <ChatDetailPanel
                        chatSessionId={selectedChatId}
                        onExecutionClick={handleExecutionClickFromChat}
                        compact={true}
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-muted-foreground">
                        <p>{t("workflow.agentCalls.selectChat")}</p>
                      </div>
                    )}
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
