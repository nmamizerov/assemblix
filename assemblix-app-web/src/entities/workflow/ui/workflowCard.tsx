import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { Calendar } from "lucide-react";
import { FileText, WorkflowIcon } from "lucide-react";
import type { Workflow } from "../model/types";
import { WorkflowActions } from "./actions/workflow-actions";

interface WorkflowCardProps {
  workflow: Workflow;
  onRefetch?: () => void;
}

export const WorkflowCard = ({ workflow, onRefetch }: WorkflowCardProps) => {
  const { t } = useTranslation();
  const { formatShortDateTime } = useFormatDate();

  return (
    <div className="group relative flex cursor-pointer items-start gap-4 rounded-lg border border-border bg-card p-6 transition-all duration-200 hover:border-primary/50 hover:shadow-md">
      <div className="rounded-md bg-primary/10 p-2 transition-colors group-hover:bg-primary/20">
        {workflow.isTemplate ? (
          <FileText className="h-5 w-5 text-primary" />
        ) : (
          <WorkflowIcon className="h-5 w-5 text-primary" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="mb-1 truncate font-semibold text-card-foreground">
          {workflow.name}
        </h3>
        <p className="line-clamp-2 text-sm text-muted-foreground">
          {workflow.description || t("workflowCard.noDescription")}
        </p>
        <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
          <Calendar className="h-3 w-3" />
          <span>
            {formatShortDateTime(workflow.updatedAt)}
          </span>
        </div>
      </div>
      <div
        className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => e.preventDefault()}
      >
        <WorkflowActions workflow={workflow} onRefetch={onRefetch} />
      </div>
    </div>
  );
};
