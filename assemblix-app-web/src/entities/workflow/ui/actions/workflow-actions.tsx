import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { MoreHorizontal, Pencil, Copy, Loader2, Trash2, FolderInput } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip";
import { RenameWorkflowModal } from "./rename-workflow-modal";
import { DeleteWorkflowModal } from "./delete-workflow-modal";
import { MoveWorkflowModal } from "./move-workflow-modal";
import { useCopyWorkflowMutation } from "../../api/workflow.api";
import type { Workflow } from "../../model/types";
import { toast } from "sonner";

interface WorkflowActionsProps {
  workflow: Workflow;
  onRefetch?: () => void;
}

export const WorkflowActions = ({
  workflow,
  onRefetch,
}: WorkflowActionsProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isMoveModalOpen, setIsMoveModalOpen] = useState(false);
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [copyWorkflow, { isLoading: isCopying }] = useCopyWorkflowMutation();

  const handleRenameClick = () => {
    setIsPopoverOpen(false);
    setIsRenameModalOpen(true);
  };

  const handleRenameSuccess = () => {
    if (onRefetch) {
      onRefetch();
    }
  };

  const handleDuplicateClick = async () => {
    setIsPopoverOpen(false);
    try {
      const duplicatedWorkflow = await copyWorkflow(workflow.id).unwrap();
      toast.success(t("workflowActions.duplicateSuccess"));
      navigate(`/projects/${projectId}/workflows/${duplicatedWorkflow.id}`);
    } catch (error) {
      toast.error(t("workflowActions.duplicateError"));
      console.error("Failed to duplicate workflow:", error);
    }
  };

  const handleMoveClick = () => {
    setIsPopoverOpen(false);
    setIsMoveModalOpen(true);
  };

  const handleDeleteClick = () => {
    setIsPopoverOpen(false);
    setIsDeleteModalOpen(true);
  };

  const handleDeleteSuccess = () => {
    if (onRefetch) {
      onRefetch();
    }
    // Редирект на страницу со списком агентов
    navigate(`/projects/${projectId}/workflows`);
  };

  return (
    <>
      <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
        <Tooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="size-5" />
              </Button>
            </PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent>
            <p>{t("workflowActions.additionalActions")}</p>
          </TooltipContent>
        </Tooltip>
        <PopoverContent className="w-48 p-2" align="end">
          <button
            onClick={handleRenameClick}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-accent transition-colors"
          >
            <Pencil className="h-4 w-4" />
            {t("workflowActions.rename")}
          </button>
          <button
            onClick={handleDuplicateClick}
            disabled={isCopying}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCopying ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
            {t("workflowActions.duplicate")}
          </button>
          <button
            onClick={handleMoveClick}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-accent transition-colors"
          >
            <FolderInput className="h-4 w-4" />
            {t("workflowActions.move")}
          </button>
          <div className="h-px bg-border my-1" />
          <button
            onClick={handleDeleteClick}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-destructive/10 text-destructive transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            {t("workflowActions.delete")}
          </button>
        </PopoverContent>
      </Popover>

      <RenameWorkflowModal
        workflow={workflow}
        open={isRenameModalOpen}
        onOpenChange={setIsRenameModalOpen}
        onSuccess={handleRenameSuccess}
      />

      <DeleteWorkflowModal
        workflow={workflow}
        open={isDeleteModalOpen}
        onOpenChange={setIsDeleteModalOpen}
        onSuccess={handleDeleteSuccess}
      />

      <MoveWorkflowModal
        workflow={workflow}
        open={isMoveModalOpen}
        onOpenChange={setIsMoveModalOpen}
      />
    </>
  );
};
