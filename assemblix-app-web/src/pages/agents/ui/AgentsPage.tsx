import { Loader2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";

import { useGetWorkflowsQuery, WorkflowCard } from "@/entities/workflow";
import { selectCurrentProjectId } from "@/entities/organization";

export const AgentsPage = () => {
  const { t } = useTranslation();
  const { projectId } = useParams();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const {
    data: workflows = [],
    isLoading,
    refetch,
  } = useGetWorkflowsQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (workflows.length === 0) {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
        <p className="text-sm text-muted-foreground">{t("agents.noAgents")}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {workflows.map((workflow) => (
        <Link key={workflow.id} to={`/projects/${projectId}/workflows/${workflow.id}`}>
          <WorkflowCard workflow={workflow} onRefetch={refetch} />
        </Link>
      ))}
    </div>
  );
};
