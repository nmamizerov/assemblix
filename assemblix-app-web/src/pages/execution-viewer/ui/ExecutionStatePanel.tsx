import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { JsonViewer } from "@/shared/ui/json-viewer";
import { JsonDiffViewer } from "@/shared/ui/json-diff-viewer";
import { cn } from "@/shared/lib/utils";
import type { ExecutionStepResponse } from "@/entities/execution";
import { STATE_DIFF_NODE_TYPES } from "@/entities/workflow/lib/workflow-editor/model/config";
import { useNodeDisplay } from "@/entities/workflow/lib/workflow-editor/lib/use-node-display";
import type { NodeType } from "@/entities/workflow/model/types";

interface ExecutionStatePanelProps {
  step: ExecutionStepResponse;
}

export const ExecutionStatePanel = ({ step }: ExecutionStatePanelProps) => {
  const { t } = useTranslation();
  const [showFullState, setShowFullState] = useState(false);
  const { Icon: NodeIcon, color } = useNodeDisplay(step.nodeType);
  const showDiff = STATE_DIFF_NODE_TYPES.includes(step.nodeType as NodeType);

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.15, ease: "easeInOut" }}
      className="absolute top-4 bottom-4 left-4 z-30 flex w-[380px] flex-col overflow-hidden rounded-xl border border-border bg-panel shadow-lg"
    >
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
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
            {t("executionViewer.currentState")}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t("executionViewer.stateAfterStep")} {step.stepNumber}
          </p>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="px-4 py-4">
          {showDiff ? (
            <>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("executionViewer.stateChanges")}
              </h4>
              <JsonDiffViewer
                before={step.stateBefore}
                after={step.stateAfter ?? {}}
              />

              {/* Full state (collapsible) */}
              <button
                onClick={() => setShowFullState((prev) => !prev)}
                className="mt-4 flex w-full items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {showFullState ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
                {t("executionViewer.fullState")}
              </button>
              {showFullState && (
                <div className="mt-2">
                  <JsonViewer
                    data={step.stateAfter ?? {}}
                    defaultExpanded={false}
                  />
                </div>
              )}
            </>
          ) : (
            <>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("executionViewer.fullState")}
              </h4>
              <JsonViewer data={step.stateAfter ?? {}} defaultExpanded={true} />
            </>
          )}
        </div>
      </ScrollArea>
    </motion.div>
  );
};
