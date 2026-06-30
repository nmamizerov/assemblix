import {
  Loader2,
  Coins,
  Circle,
  CheckCircle2,
  XCircle,
  Clock,
  ListChecks,
  UsersRound,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { useGetExecutionsQuery, ExecutionStatus } from "@/entities/execution";
import { selectCurrentProjectId } from "@/entities/organization";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/ui/tooltip";
import { Pagination } from "@/shared/ui";
import { useFormatDate } from "@/shared/lib/format-date";

const formatDuration = (durationMs: number): string => {
  const seconds = Math.floor(durationMs / 1000);
  if (seconds < 60) {
    return `${seconds} сек`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes} мин ${remainingSeconds} сек`;
};

interface ExecutionsListProps {
  workflowId?: string;
  includeDebug?: boolean;
  showInfoBanner?: boolean;
  clientId?: string;
  onItemClick?: (executionId: string) => void;
}

export const ExecutionsList = ({
  workflowId,
  includeDebug = false,
  clientId,
  onItemClick,
}: ExecutionsListProps) => {
  const { t } = useTranslation();
  const { formatShortDateTime, formatNumber } = useFormatDate();
  const { projectId } = useParams();
  const [currentPage, setCurrentPage] = useState(1);
  const limit = 10;
  const currentProjectId = useSelector(selectCurrentProjectId);

  const getStatusConfig = (status: ExecutionStatus) => {
    switch (status) {
      case ExecutionStatus.PENDING:
        return {
          label: t("executions.statuses.pending"),
          className:
            "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
          icon: Clock,
          iconClassName: "h-3.5 w-3.5 text-gray-600 dark:text-gray-400",
        };
      case ExecutionStatus.RUNNING:
        return {
          label: t("executions.statuses.running"),
          className:
            "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
          icon: Circle,
          iconClassName:
            "h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400 animate-pulse",
        };
      case ExecutionStatus.COMPLETED:
        return {
          label: t("executions.statuses.completed"),
          className:
            "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
          icon: CheckCircle2,
          iconClassName: "h-3.5 w-3.5 text-green-600 dark:text-green-400",
        };
      case ExecutionStatus.FAILED:
        return {
          label: t("executions.statuses.failed"),
          className:
            "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
          icon: XCircle,
          iconClassName: "h-3.5 w-3.5 text-red-600 dark:text-red-400",
        };
      default:
        return {
          label: status,
          className:
            "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
          icon: Circle,
          iconClassName: "h-3.5 w-3.5 text-gray-600 dark:text-gray-400",
        };
    }
  };

  const { data, isLoading } = useGetExecutionsQuery(
    {
      projectId: currentProjectId!,
      page: currentPage,
      limit,
      includeDebug,
      workflowId,
      clientId,
    },
    { skip: !currentProjectId },
  );

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const executions = data?.data || [];

  if (executions.length === 0) {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
        <p className="text-sm text-muted-foreground">
          {workflowId
            ? t("workflow.agentCalls.noExecutions")
            : t("executions.noExecutions")}
        </p>
      </div>
    );
  }

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Список вызовов */}
      <TooltipProvider>
        {executions.map((execution) => {
          const statusConfig = getStatusConfig(execution.status);
          const StatusIcon = statusConfig.icon;

          const formattedDate = formatShortDateTime(execution.startedAt);

          const content = (
            <div
              className="group flex cursor-pointer items-center justify-between rounded-lg border border-border bg-card px-4 py-3 transition-all duration-200 hover:border-primary/50 hover:shadow-md"
              onClick={
                onItemClick ? () => onItemClick(execution.id) : undefined
              }
            >
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-card-foreground">
                    {execution.workflow.name}
                  </span>
                  <div
                    className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${statusConfig.className}`}
                  >
                    <StatusIcon className={statusConfig.iconClassName} />
                    {statusConfig.label}
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {execution.clientSessionId && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Link
                          to={`/projects/${projectId}/client-sessions/${encodeURIComponent(
                            execution.clientSessionId,
                          )}`}
                          className="flex items-center gap-1 text-muted-foreground hover:text-primary"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <UsersRound className="h-3.5 w-3.5" />
                          <span className="text-xs font-mono">
                            {execution.clientSessionId}
                          </span>
                        </Link>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>{t("executions.clientSession")}</p>
                      </TooltipContent>
                    </Tooltip>
                  )}

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <ListChecks className="h-3.5 w-3.5" />
                        <span className="text-xs">{execution.stepsCount}</span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>
                        {t("executions.steps")} {execution.stepsCount}
                      </p>
                    </TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Clock className="h-3.5 w-3.5" />
                        <span className="text-xs">
                          {formatDuration(execution.durationMs)}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>
                        {t("executionViewer.duration")}:{" "}
                        {formatDuration(execution.durationMs)}
                      </p>
                    </TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Coins className="h-3.5 w-3.5" />
                        <span className="text-xs">
                          {formatNumber(execution.totalCredits ?? 0)}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>
                        {t("executions.credits")}{" "}
                        {formatNumber(execution.totalCredits ?? 0)}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>

              <span className="text-xs text-muted-foreground">
                {formattedDate}
              </span>
            </div>
          );

          return onItemClick ? (
            <div key={execution.id}>{content}</div>
          ) : (
            <Link
              key={execution.id}
              to={`/projects/${projectId}/workflows/${execution.workflowId}/executions/${execution.id}`}
              state={{ from: "/sessions" }}
            >
              {content}
            </Link>
          );
        })}
      </TooltipProvider>

      {/* Пагинация */}
      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={setCurrentPage}
      />
    </div>
  );
};
