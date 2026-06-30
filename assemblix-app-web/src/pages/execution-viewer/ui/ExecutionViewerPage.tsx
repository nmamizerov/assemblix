import { useState } from "react";
import { useParams } from "react-router-dom";
import { Loader2, AlertCircle } from "lucide-react";
import { AnimatePresence } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useGetExecutionDetailQuery } from "@/entities/execution";
import { WorkflowEditorCanvas } from "@/entities/workflow";
import { ExecutionViewerHeader } from "./ExecutionViewerHeader";
import { ExecutionLogPanel } from "./ExecutionLogPanel";
import { ExecutionStatePanel } from "./ExecutionStatePanel";
import type { Workflow } from "@/entities/workflow/model/types";

export const ExecutionViewerPage = () => {
  const { t } = useTranslation();
  const { executionId } = useParams<{ executionId: string }>();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const {
    data: execution,
    isLoading,
    isError,
    error,
  } = useGetExecutionDetailQuery(executionId || "");

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (isError || !execution) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
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
    <div className="flex h-screen w-full flex-col bg-background">
      <ExecutionViewerHeader execution={execution} />
      <div className="relative flex-1 overflow-hidden">
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
