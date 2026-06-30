import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useSelector } from "react-redux";
import { Loader2, X, FolderInput } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Button } from "@/shared/ui/button";
import { useGetProjectsQuery } from "@/entities/project";
import { selectCurrentProjectId } from "@/entities/organization";
import { useMoveWorkflowMutation } from "../../api/workflow.api";
import type { Workflow } from "../../model/types";

interface MoveWorkflowModalProps {
  workflow: Workflow;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export const MoveWorkflowModal = ({
  workflow,
  open,
  onOpenChange,
  onSuccess,
}: MoveWorkflowModalProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  const { data: projects = [] } = useGetProjectsQuery({});
  const [moveWorkflow, { isLoading }] = useMoveWorkflowMutation();

  const availableProjects = projects.filter(
    (project) => project.id !== currentProjectId,
  );

  const handleMove = async () => {
    if (!selectedProjectId) return;

    try {
      await moveWorkflow({
        workflowId: workflow.id,
        targetProjectId: selectedProjectId,
      }).unwrap();

      toast.success(t("workflowActions.moveSuccess"));
      onOpenChange(false);
      setSelectedProjectId("");

      if (onSuccess) {
        onSuccess();
      }

      navigate(`/projects/${projectId}/workflows`);
    } catch (error) {
      console.error(error);
      toast.error(t("workflowActions.moveError"));
    }
  };

  const handleCancel = () => {
    onOpenChange(false);
    setSelectedProjectId("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("workflowActions.moveAgent")}</DialogTitle>
          <DialogDescription>
            {t("workflowActions.moveDescription")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">
              {t("workflowActions.moveProjectLabel")}
            </label>
            <Select
              value={selectedProjectId}
              onValueChange={setSelectedProjectId}
            >
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={t("workflowActions.moveProjectPlaceholder")}
                />
              </SelectTrigger>
              <SelectContent>
                {availableProjects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-2 justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={isLoading}
              className="gap-2"
            >
              <X className="h-4 w-4" />
              {t("workflowActions.cancel")}
            </Button>
            <Button
              type="button"
              onClick={handleMove}
              disabled={isLoading || !selectedProjectId}
              className="gap-2"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FolderInput className="h-4 w-4" />
              )}
              {t("workflowActions.moveConfirm")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
