import { useState } from "react";
import { motion } from "framer-motion";
import { X, Clock, DollarSign, AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/shared/ui/button";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { JsonViewer } from "@/shared/ui/json-viewer";
import { cn } from "@/shared/lib/utils";
import { useFormatDate } from "@/shared/lib/format-date";
import type { ExecutionStepResponse } from "@/entities/execution";
import { useNodeDisplay } from "@/entities/workflow/lib/workflow-editor/lib/use-node-display";
import {
  getStepStatusColor,
  getStepStatusLabel,
} from "../lib/execution-status-utils.tsx";

interface ExecutionLogPanelProps {
  step: ExecutionStepResponse;
  onClose: () => void;
}

export const ExecutionLogPanel = ({ step, onClose }: ExecutionLogPanelProps) => {
  const { t } = useTranslation();
  const { formatNumber } = useFormatDate();
  const [activeTab, setActiveTab] = useState<
    "input" | "output" | "cel" | "llm-request"
  >("input");
  const { Icon: NodeIcon, label: nodeLabel, color } = useNodeDisplay(
    step.nodeType,
  );

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.15, ease: "easeInOut" }}
      className="absolute top-4 right-4 bottom-4 z-30 flex w-[380px] flex-col overflow-hidden rounded-xl border border-border bg-panel shadow-lg"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex items-center justify-center rounded-md p-2",
              `bg-${color}`,
            )}
          >
            <NodeIcon className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              {t("executionViewer.stepNumber")}
              {step.stepNumber}
            </h3>
            <p className="text-xs text-muted-foreground">{nodeLabel}</p>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="px-4 py-4">
          {/* Status badge */}
          <div className="mb-4">
            <span
              className={cn(
                "inline-block rounded-full border px-3 py-1 text-xs font-medium",
                getStepStatusColor(step.status),
              )}
            >
              {getStepStatusLabel(step.status)}
            </span>
          </div>

          {/* Stats */}
          <div className="mb-4 flex flex-col gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/30 p-2.5">
              <Clock className="h-4 w-4 text-indigo-500" />
              <div>
                <p className="text-xs text-muted-foreground">
                  {t("executionViewer.duration")}
                </p>
                <p className="text-sm font-medium">{step.durationMs}ms</p>
              </div>
            </div>

            {step.credits !== null && step.credits !== undefined && (
              <div className="flex items-center gap-2 rounded-lg bg-muted/30 p-2.5">
                <DollarSign className="h-4 w-4 text-green-500" />
                <div>
                  <p className="text-xs text-muted-foreground">
                    {t("executionViewer.credits")}
                  </p>
                  <p className="text-sm font-medium">
                    {formatNumber(step.credits)}
                  </p>
                </div>
              </div>
            )}

            {step.modelUsed && (
              <div className="flex items-center gap-2 rounded-lg bg-muted/30 p-2.5">
                <div>
                  <p className="text-xs text-muted-foreground">
                    {t("executionViewer.model")}
                  </p>
                  <p className="text-sm font-medium">{step.modelUsed}</p>
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {step.errorMessage && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950/30">
              <div className="flex items-start gap-2">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
                <div>
                  <p className="text-sm font-medium text-red-900 dark:text-red-100">
                    {t("executionViewer.errorMessage")}
                  </p>
                  <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                    {step.errorMessage}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Data tabs */}
          <div className="w-full">
            <div className="mb-4 flex border-b border-border">
              <button
                onClick={() => setActiveTab("input")}
                className={cn(
                  "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
                  activeTab === "input"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {t("executionViewer.input")}
              </button>
              <button
                onClick={() => setActiveTab("output")}
                className={cn(
                  "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
                  activeTab === "output"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {t("executionViewer.output")}
              </button>
              {step.celEvaluations && (
                <button
                  onClick={() => setActiveTab("cel")}
                  className={cn(
                    "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
                    activeTab === "cel"
                      ? "border-primary text-primary"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t("executionViewer.celEvaluations")}
                </button>
              )}
              {step.llmRequest && (
                <button
                  onClick={() => setActiveTab("llm-request")}
                  className={cn(
                    "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
                    activeTab === "llm-request"
                      ? "border-primary text-primary"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t("executionViewer.llmRequest")}
                </button>
              )}
            </div>

            <div>
              {activeTab === "input" && (
                <JsonViewer
                  data={step.inputData}
                  title={t("executionViewer.input")}
                  defaultExpanded={true}
                />
              )}

              {activeTab === "output" && (
                <JsonViewer
                  data={step.outputData || {}}
                  title={t("executionViewer.output")}
                  defaultExpanded={true}
                />
              )}

              {activeTab === "cel" && step.celEvaluations && (
                <JsonViewer
                  data={step.celEvaluations}
                  title={t("executionViewer.celEvaluations")}
                  defaultExpanded={true}
                />
              )}

              {activeTab === "llm-request" && step.llmRequest && (
                <JsonViewer
                  data={step.llmRequest}
                  title={t("executionViewer.llmRequest")}
                  defaultExpanded={true}
                />
              )}
            </div>
          </div>
        </div>
      </ScrollArea>
    </motion.div>
  );
};
