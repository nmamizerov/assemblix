import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Coins, DollarSign, AlertCircle } from "lucide-react";
import { DebugStepItem } from "./debug-step-item";
import type { NodeType } from "@/entities/workflow/model/types";
import type { DebugEvent } from "../../lib/use-workflow-debug";

interface ExecutionViewerProps {
  events: DebugEvent[];
  isRunning?: boolean;
}

type DebugStep = {
  nodeType: NodeType;
  isCompleted: boolean;
  data?: Record<string, unknown>;
};

export const ExecutionViewer = ({
  events,
  isRunning,
}: ExecutionViewerProps) => {
  const { t } = useTranslation();
  // Преобразуем события в степы
  const { steps, finalMessage, totalCredits, ownKeyCostUsd, executionStatus } =
    useMemo((): {
      steps: DebugStep[];
      finalMessage: string | null;
      totalCredits: number | null;
      ownKeyCostUsd: number | null;
      executionStatus: string | null;
    } => {
      const newSteps: DebugStep[] = [];
      let completionMessage: string | null = null;
      let execTotalCredits: number | null = null;
      let execOwnKeyCostUsd: number | null = null;
      let execStatus: string | null = null;

      // Создаем карту нод по node_id для отслеживания
      const nodeMap = new Map<
        string,
        { start?: Record<string, unknown>; complete?: Record<string, unknown> }
      >();

      events.forEach((event) => {
        if (event.event_type === "step_start") {
          const nodeId = event.data?.node_id as string;
          if (nodeId) {
            if (!nodeMap.has(nodeId)) {
              nodeMap.set(nodeId, {});
            }
            nodeMap.get(nodeId)!.start = event.data;
          }
        } else if (event.event_type === "step_complete") {
          const nodeId = event.data?.node_id as string;
          if (nodeId) {
            if (!nodeMap.has(nodeId)) {
              nodeMap.set(nodeId, {});
            }
            nodeMap.get(nodeId)!.complete = event.data;
          }
        } else if (event.event_type === "execution_complete") {
          const output = event.data?.output as
            | Record<string, unknown>
            | undefined;
          completionMessage = (output?.message as string) || null;
          execTotalCredits = (event.data?.total_credits as number) ?? null;
          execOwnKeyCostUsd = (event.data?.own_key_cost_usd as number) ?? null;
          execStatus = (event.data?.status as string) ?? null;
        }
      });

      // Преобразуем карту в массив степов
      nodeMap.forEach((nodeData) => {
        const nodeType = (nodeData.start?.node_type ||
          nodeData.complete?.node_type) as NodeType;
        const nodeName = (nodeData.start?.node_name ||
          nodeData.complete?.node_name) as string;

        if (nodeData.complete) {
          // Нода завершена
          newSteps.push({
            nodeType,
            isCompleted: true,
            data: { ...nodeData.complete, node_name: nodeName },
          });
        } else if (nodeData.start) {
          // Нода начата но не завершена
          newSteps.push({
            nodeType,
            isCompleted: false,
            data: undefined,
          });
        }
      });

      return {
        steps: newSteps,
        finalMessage: completionMessage,
        totalCredits: execTotalCredits,
        ownKeyCostUsd: execOwnKeyCostUsd,
        executionStatus: execStatus,
      };
    }, [events]);

  return (
    <div className="space-y-2">
      {steps.map((step, index) => (
        <DebugStepItem
          key={index}
          nodeType={step.nodeType}
          isCompleted={step.isCompleted}
          data={step.data}
          isRunning={
            isRunning && index === steps.length - 1 && !step.isCompleted
          }
        />
      ))}

      {/* Финальное сообщение */}
      {finalMessage && (
        <div
          className={`mt-4 p-4 rounded-lg ${
            executionStatus === "error"
              ? "bg-red-100 dark:bg-red-900/40 border border-red-300 dark:border-red-700"
              : "bg-green-100 dark:bg-green-900/40 border border-green-300 dark:border-green-700"
          }`}
        >
          <div className="flex items-center gap-2 mb-3">
            {executionStatus === "error" ? (
              <AlertCircle className="size-5 text-red-600 dark:text-red-400 shrink-0" />
            ) : (
              <CheckCircle2 className="size-5 text-green-600 dark:text-green-400 shrink-0" />
            )}
            <p
              className={`text-sm font-semibold ${
                executionStatus === "error"
                  ? "text-red-900 dark:text-red-100"
                  : "text-green-900 dark:text-green-100"
              }`}
            >
              {executionStatus === "error"
                ? t("debug.executionError")
                : t("debug.executionResult")}
            </p>
          </div>
          <div
            className={`p-3 bg-white dark:bg-gray-800 rounded border ${
              executionStatus === "error"
                ? "border-red-200 dark:border-red-800"
                : "border-green-200 dark:border-green-800"
            }`}
          >
            <p className="text-sm text-foreground whitespace-pre-wrap wrap-anywhere">
              {finalMessage}
            </p>
          </div>

          {/* Информация о стоимости */}
          {(totalCredits !== null || ownKeyCostUsd !== null) && (
            <div
              className={`mt-3 pt-3 border-t ${
                executionStatus === "error"
                  ? "border-red-300 dark:border-red-700"
                  : "border-green-300 dark:border-green-700"
              }`}
            >
              <div className="flex items-center gap-4 text-xs">
                {typeof totalCredits === "number" && totalCredits > 0 && (
                  <div
                    className={`flex items-center gap-1.5 ${
                      executionStatus === "error"
                        ? "text-red-800 dark:text-red-200"
                        : "text-green-800 dark:text-green-200"
                    }`}
                  >
                    <Coins className="size-4" />
                    <span className="font-medium">
                      {totalCredits.toFixed(4)} {t("debug.creditsUsed")}
                    </span>
                  </div>
                )}
                {typeof ownKeyCostUsd === "number" && ownKeyCostUsd > 0 && (
                  <div
                    className={`flex items-center gap-1.5 ${
                      executionStatus === "error"
                        ? "text-red-800 dark:text-red-200"
                        : "text-green-800 dark:text-green-200"
                    }`}
                  >
                    <DollarSign className="size-4" />
                    <span className="font-medium">
                      ${ownKeyCostUsd.toFixed(6)} {t("debug.ownKeyCost")}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
