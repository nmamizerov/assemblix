import { useGetWorkflowQuery, WorkflowEditorCanvas } from "@/entities/workflow";
import { useParams, useNavigate } from "react-router-dom";
import { Loader2, AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/shared/ui/button";
import { useState, useEffect } from "react";
import type { Workflow } from "@/entities/workflow";
import { toast } from "sonner";
import { useSelector } from "react-redux";
import { selectAccessToken } from "@/entities/session";

export const WorkflowDetailsPage = () => {
  const { t } = useTranslation();
  const { workflowId, projectId } = useParams();
  const navigate = useNavigate();
  const accessToken = useSelector(selectAccessToken);
  const {
    data: initialWorkflow,
    isError,
    isLoading,
    error,
    refetch,
  } = useGetWorkflowQuery(workflowId!, {
    refetchOnMountOrArgChange: true,
  });

  const [currentWorkflow, setCurrentWorkflow] = useState<Workflow | undefined>(
    initialWorkflow
  );
  const [isViewingVersion, setIsViewingVersion] = useState(false);

  // Обновляем текущий workflow при изменении начального
  useEffect(() => {
    if (initialWorkflow) {
      setCurrentWorkflow(initialWorkflow);
    }
  }, [initialWorkflow]);

  // Функция для загрузки конкретной версии
  const handleLoadVersion = async (versionId: string) => {
    setIsViewingVersion(true);
    try {
      // Используем RTK Query для загрузки версии
      const result = await fetch(`/api/workflows/${versionId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!result.ok) {
        throw new Error("Failed to load version");
      }

      const versionWorkflow = await result.json();
      setCurrentWorkflow((workflow) => ({
        ...versionWorkflow,
        id: workflow?.id,
        versions: workflow?.versions,
      }));
    } catch (error) {
      console.error(error);
      toast.error(t("workflow.details.versionLoadError"), {
        description: t("workflow.details.versionLoadErrorDescription"),
      });
    }
  };

  const handleRefetch = () => {
    refetch();
  };

  const handleCanvasChange = () => {
    setIsViewingVersion(false);
  };

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 text-center px-4">
        <div className="bg-destructive/10 p-4 rounded-full">
          <AlertCircle className="w-10 h-10 text-destructive" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-tight">
            {t("workflow.details.loadingError")}
          </h2>
          <p className="text-muted-foreground max-w-[400px]">
            {/* @ts-expect-error error type is unknown */}
            {error?.data?.message ||
              t("workflow.details.loadingErrorDescription")}
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate(`/projects/${projectId}/workflows`)}>
          {t("workflow.details.backToList")}
        </Button>
      </div>
    );
  }

  if (isLoading || !currentWorkflow) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <WorkflowEditorCanvas
      workflow={currentWorkflow}
      onRefetch={handleRefetch}
      onLoadVersion={handleLoadVersion}
      onCanvasChange={handleCanvasChange}
      isDraft={!isViewingVersion}
    />
  );
};
