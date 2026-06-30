import { useTranslation } from "react-i18next";
import { Loader2, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { useDeleteWorkflowMutation } from "../../api/workflow.api";
import type { Workflow } from "../../model/types";

interface DeleteWorkflowModalProps {
  workflow: Workflow;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export const DeleteWorkflowModal = ({
  workflow,
  open,
  onOpenChange,
  onSuccess,
}: DeleteWorkflowModalProps) => {
  const { t } = useTranslation();
  const [deleteWorkflow, { isLoading }] = useDeleteWorkflowMutation();

  const handleDelete = async () => {
    try {
      await deleteWorkflow(workflow.id).unwrap();

      toast.success(t("workflowActions.deleted"));
      onOpenChange(false);

      // Вызываем callback для рефетча данных или редиректа
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      console.error(error);
      toast.error(t("versionsDropdown.error"), {
        description: t("workflowActions.deleteError"),
      });
    }
  };

  const handleCancel = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-destructive">
            {t("workflowActions.deleteAgent")}
          </DialogTitle>
          <DialogDescription>
            {t("workflowActions.deleteDescription", { name: workflow.name })}
          </DialogDescription>
        </DialogHeader>

        <div className="bg-destructive/10 border border-destructive/20 rounded-md p-3 text-sm text-destructive">
          {t("workflowActions.deleteWarning")}
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
            variant="destructive"
            onClick={handleDelete}
            disabled={isLoading}
            className="gap-2"
          >
            {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            <Trash2 className="h-4 w-4" />
            {t("workflowActions.deleteConfirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
