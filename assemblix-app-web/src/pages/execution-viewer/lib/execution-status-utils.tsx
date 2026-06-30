import { CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";
import i18n from "@/shared/i18n";
import type { ExecutionStatus, StepStatus } from "@/entities/execution";

export const getStatusIcon = (status: ExecutionStatus) => {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case "failed":
      return <XCircle className="h-5 w-5 text-red-500" />;
    case "running":
      return <Loader2 className="h-5 w-5 text-orange-500 animate-spin" />;
    default:
      return <Clock className="h-5 w-5 text-gray-500" />;
  }
};

export const getExecutionStatusLabel = (status: ExecutionStatus): string => {
  switch (status) {
    case "completed":
      return i18n.t("executions.statuses.completed");
    case "failed":
      return i18n.t("executions.statuses.failed");
    case "running":
      return i18n.t("executions.statuses.running");
    case "pending":
      return i18n.t("executions.statuses.pending");
    default:
      return status;
  }
};

export const getStepStatusLabel = (status: StepStatus): string => {
  switch (status) {
    case "completed":
      return i18n.t("executions.statuses.completed");
    case "failed":
      return i18n.t("executions.statuses.failed");
    case "running":
      return i18n.t("executions.statuses.running");
    case "pending":
      return i18n.t("executions.statuses.pending");
    default:
      return status;
  }
};

export const getExecutionStatusColor = (status: ExecutionStatus): string => {
  switch (status) {
    case "completed":
      return "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
    case "failed":
      return "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800";
    case "running":
      return "text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-950/30 border-orange-200 dark:border-orange-800";
    default:
      return "text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-950/30 border-gray-200 dark:border-gray-800";
  }
};

export const getStepStatusColor = (status: StepStatus): string => {
  switch (status) {
    case "completed":
      return "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
    case "failed":
      return "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800";
    case "running":
      return "text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-950/30 border-orange-200 dark:border-orange-800";
    default:
      return "text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-950/30 border-gray-200 dark:border-gray-800";
  }
};
