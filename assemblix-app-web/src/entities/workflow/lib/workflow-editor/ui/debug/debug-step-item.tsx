import { useState } from "react";
import {
  Loader2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Coins,
  DollarSign,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/utils";
import { useNodeDisplay } from "../../lib/use-node-display";
import { NodeType } from "@/entities/workflow/model/types";
import { JsonViewer } from "@/shared/ui/json-viewer";

interface DebugStepItemProps {
  nodeType: NodeType;
  isCompleted: boolean;
  data?: Record<string, unknown>;
  isRunning?: boolean;
}

export const DebugStepItem = ({
  nodeType,
  isCompleted,
  data,
  isRunning,
}: DebugStepItemProps) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);

  const { Icon: NodeIcon, label: nodeLabel, color } = useNodeDisplay(nodeType);
  const nodeName = data?.node_name as string | undefined;
  const duration = data?.duration_ms
    ? `${Math.round(data.duration_ms as number)}ms`
    : undefined;

  const inputData = data?.input_data as Record<string, unknown> | undefined;
  const outputData = data?.output_data as Record<string, unknown> | undefined;
  const stateBefore = data?.state_before as Record<string, unknown> | undefined;
  const stateAfter = data?.state_after as Record<string, unknown> | undefined;
  const projectStateAfter = data?.project_state_after as
    | Record<string, unknown>
    | undefined;

  // Извлекаем данные о стоимости для LLM нод
  const creditsUsed = data?.credits_used as number | undefined;
  const ownKeyCostUsd = data?.own_key_cost_usd as number | undefined;
  const isLLMNode = nodeType === NodeType.AGENT;

  // Проверяем, что в projectStateAfter есть хотя бы 1 ключ
  const hasProjectState =
    projectStateAfter && Object.keys(projectStateAfter).length > 0;

  const hasExpandableData =
    isCompleted &&
    (inputData || outputData || stateBefore || stateAfter || hasProjectState);

  const handleToggle = () => {
    if (hasExpandableData) {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div
      className={cn(
        "border rounded-lg transition-all",
        isCompleted
          ? "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800"
          : "bg-orange-50 dark:bg-orange-950/30 border-orange-200 dark:border-orange-800",
      )}
    >
      {/* Заголовок */}
      <div
        className={cn(
          "flex items-center gap-3 p-3",
          hasExpandableData && "cursor-pointer hover:opacity-80",
        )}
        onClick={handleToggle}
      >
        <div className={cn("p-1.5 rounded-md shrink-0", `bg-${color}`)}>
          <NodeIcon className="size-4 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p
            className={cn(
              "text-sm font-medium",
              isCompleted
                ? "text-green-900 dark:text-green-100"
                : "text-orange-900 dark:text-orange-100",
            )}
          >
            {nodeName || nodeLabel}
          </p>
          <div
            className={cn(
              "text-xs flex items-center gap-1.5 flex-wrap",
              isCompleted
                ? "text-green-700 dark:text-green-300"
                : "text-orange-700 dark:text-orange-300",
            )}
          >
            <span>{nodeLabel}</span>
            {duration && (
              <>
                <span>•</span>
                <span>{duration}</span>
              </>
            )}
            {isLLMNode &&
              isCompleted &&
              creditsUsed !== undefined &&
              creditsUsed > 0 && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Coins className="size-3" />
                    {creditsUsed.toFixed(4)}
                  </span>
                </>
              )}
            {isLLMNode &&
              isCompleted &&
              ownKeyCostUsd !== undefined &&
              ownKeyCostUsd > 0 && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <DollarSign className="size-3" />
                    {ownKeyCostUsd.toFixed(6)}
                  </span>
                </>
              )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isCompleted ? (
            <CheckCircle2
              className={cn("size-5", "text-green-600 dark:text-green-400")}
            />
          ) : isRunning ? (
            <Loader2
              className={cn(
                "size-5 animate-spin",
                "text-orange-600 dark:text-orange-400",
              )}
            />
          ) : (
            <div className="size-5" />
          )}
          {hasExpandableData &&
            (isExpanded ? (
              <ChevronDown className="size-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="size-4 text-muted-foreground" />
            ))}
        </div>
      </div>

      {/* Раскрываемый контент */}
      {isExpanded && hasExpandableData && (
        <div className="px-3 pb-3 space-y-3 border-t border-green-200 dark:border-green-800 pt-3">
          {inputData && (
            <div>
              <h4 className="text-xs font-semibold text-green-900 dark:text-green-100 mb-2">
                {t("debug.inputData")}
              </h4>
              <JsonViewer data={inputData} defaultExpanded={false} />
            </div>
          )}

          {outputData && (
            <div>
              <h4 className="text-xs font-semibold text-green-900 dark:text-green-100 mb-2">
                {t("debug.outputData")}
              </h4>
              <JsonViewer data={outputData} defaultExpanded={false} />
            </div>
          )}

          {stateBefore && (
            <div>
              <h4 className="text-xs font-semibold text-green-900 dark:text-green-100 mb-2">
                {t("debug.stateBefore")}
              </h4>
              <JsonViewer data={stateBefore} defaultExpanded={false} />
            </div>
          )}

          {stateAfter && (
            <div>
              <h4 className="text-xs font-semibold text-green-900 dark:text-green-100 mb-2">
                {t("debug.stateAfter")}
              </h4>
              <JsonViewer data={stateAfter} defaultExpanded={false} />
            </div>
          )}

          {hasProjectState && (
            <div>
              <h4 className="text-xs font-semibold text-green-900 dark:text-green-100 mb-2">
                {t("debug.projectStateAfter")}
              </h4>
              <JsonViewer data={projectStateAfter} defaultExpanded={false} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
