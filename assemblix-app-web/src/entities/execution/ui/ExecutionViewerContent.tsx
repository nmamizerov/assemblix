import { useState } from "react";
import {
  Loader2,
  AlertCircle,
  ArrowLeft,
  Clock,
  DollarSign,
} from "lucide-react";
import { AnimatePresence } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useGetExecutionDetailQuery } from "@/entities/execution";
import { WorkflowEditorCanvas } from "@/entities/workflow";
import { ExecutionLogPanel } from "@/pages/execution-viewer/ui/ExecutionLogPanel";
import { ExecutionStatePanel } from "@/pages/execution-viewer/ui/ExecutionStatePanel";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/utils";
import { useFormatDate } from "@/shared/lib/format-date";
import type { Workflow } from "@/entities/workflow/model/types";
import {
  getStatusIcon,
  getExecutionStatusLabel,
  getExecutionStatusColor,
} from "@/pages/execution-viewer/lib/execution-status-utils";

interface ExecutionViewerContentProps {
  executionId: string;
  onBack: () => void;
}

export const ExecutionViewerContent = ({
  executionId,
  onBack,
}: ExecutionViewerContentProps) => {
  const { t } = useTranslation();
  const { formatDateTime, formatNumber } = useFormatDate();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const {
    data: execution,
    isLoading,
    isError,
    error,
  } = useGetExecutionDetailQuery(executionId || "");

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };


  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (isError || !execution) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-center px-4">
          <div className="bg-destructive/10 p-4 rounded-full">
            <AlertCircle className="w-10 h-10 text-destructive" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-semibold tracking-tight">
              {t("executionViewer.loadingError")}
            </h2>
            <p className="text-muted-foreground max-w-[400px]">
              {/* @ts-expect-error error type is unknown */}
              {error?.data?.message ||
                t("executionViewer.loadingErrorDescription")}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Преобразуем workflow из execution в формат Workflow
  const workflow: Workflow = {
    ...execution.workflow,
    nodes: (execution.workflow.nodes as Workflow["nodes"]) || [],
    edges: (execution.workflow.edges as Workflow["edges"]) || [],
    isTemplate: false,
    state: [],
  };

  const selectedStep = selectedNodeId
    ? execution.steps.find((s) => s.nodeId === selectedNodeId)
    : null;

  const handleNodeClick = (nodeId: string) => {
    if (nodeId === "") {
      setSelectedNodeId(null);
    } else {
      setSelectedNodeId(nodeId);
    }
  };

  return (
    <div className="relative w-full h-full flex flex-col bg-background">
      {/* Header */}
      <div className="bg-card border-b border-border shadow-sm shrink-0">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Левая часть - название и кнопка назад */}
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                className="shrink-0"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                {t("executionViewer.back")}
              </Button>
              <div className="flex flex-col">
                <h2 className="text-xl font-semibold text-foreground">
                  {execution.workflow.name}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {t("executionViewer.executionFrom")}{" "}
                  {formatDateTime(execution.startedAt)}
                </p>
              </div>
            </div>

            {/* Правая часть - статус и метрики */}
            <div className="flex items-center gap-6">
              {/* Статус */}
              <div
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border",
                  getExecutionStatusColor(execution.status),
                )}
              >
                {getStatusIcon(execution.status)}
                {getExecutionStatusLabel(execution.status)}
              </div>

              {/* Метрики */}
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {t("executionViewer.duration")}
                    </p>
                    <p className="text-sm font-medium">
                      {formatDuration(execution.durationMs)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {t("executionViewer.credits")}
                    </p>
                    <p className="text-sm font-medium">
                      {formatNumber(execution.totalCredits ?? 0)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {t("executionViewer.steps")}
                    </p>
                    <p className="text-sm font-medium">
                      {execution.stepsCount}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Сообщение об ошибке */}
          {execution.status === "failed" && execution.errorMessage && (
            <div className="mt-3 p-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30">
              <p className="text-sm font-medium text-red-900 dark:text-red-100">
                {t("executionViewer.errorExecution")}
              </p>
              <p className="text-sm text-red-700 dark:text-red-300 mt-1">
                {execution.errorMessage}
              </p>
              {execution.failedNodeId && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                  {t("executionViewer.errorInNode")} {execution.failedNodeId}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative overflow-hidden">
        <WorkflowEditorCanvas
          workflow={workflow}
          mode="view"
          executionSteps={execution.steps}
          onNodeClick={handleNodeClick}
        />
        <AnimatePresence>
          {selectedStep && (
            <ExecutionStatePanel
              key={`state-${selectedStep.id}`}
              step={selectedStep}
            />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {selectedStep && (
            <ExecutionLogPanel
              key={`log-${selectedStep.id}`}
              step={selectedStep}
              onClose={() => setSelectedNodeId(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
