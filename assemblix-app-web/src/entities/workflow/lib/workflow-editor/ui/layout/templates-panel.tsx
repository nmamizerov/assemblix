import { useState } from "react";
import { Panel } from "@xyflow/react";
import { cn } from "@/shared/lib/utils";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { MoreHorizontal, Loader2, X, Pencil, Copy, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
  useGetNodeTemplatesQuery,
  useDeleteNodeTemplateMutation,
  type NodeTemplate,
  EditTemplateModal,
  DuplicateTemplateModal,
} from "@/entities/node-template";
import { selectCurrentProjectId } from "@/entities/organization";
import { getNodeConfig } from "../../model/config";
import { NodeType } from "@/entities/workflow/model/types";
import { Button } from "@/shared/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";

interface TemplatesPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const TemplatesPanel = ({ isOpen, onClose }: TemplatesPanelProps) => {
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const [templateToDelete, setTemplateToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [templateToEdit, setTemplateToEdit] = useState<NodeTemplate | null>(
    null,
  );
  const [templateToDuplicate, setTemplateToDuplicate] =
    useState<NodeTemplate | null>(null);
  const [openPopoverId, setOpenPopoverId] = useState<string | null>(null);

  const { data: templates, isLoading } = useGetNodeTemplatesQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId },
  );

  const [deleteTemplate, { isLoading: isDeleting }] =
    useDeleteNodeTemplateMutation();

  const NODE_CONFIG = getNodeConfig();

  const onDragStart = (
    event: React.DragEvent<HTMLDivElement>,
    template: NodeTemplate,
  ) => {
    event.dataTransfer.setData(
      "application/reactflow-template",
      JSON.stringify(template.config),
    );
    event.dataTransfer.effectAllowed = "move";
  };

  const handleDelete = async () => {
    if (!templateToDelete) return;

    try {
      await deleteTemplate(templateToDelete.id).unwrap();
      toast.success(t("nodeTemplates.deleteSuccess"));
      setTemplateToDelete(null);
    } catch (error) {
      console.error(error);
      toast.error(t("nodeTemplates.deleteError"));
    }
  };

  const handleEditClick = (template: NodeTemplate) => {
    setOpenPopoverId(null);
    setTemplateToEdit(template);
  };

  const handleDuplicateClick = (template: NodeTemplate) => {
    setOpenPopoverId(null);
    setTemplateToDuplicate(template);
  };

  const handleDeleteClick = (template: NodeTemplate) => {
    setOpenPopoverId(null);
    setTemplateToDelete({
      id: template.id,
      name: template.name,
    });
  };

  if (!isOpen) return null;

  return (
    <>
      <Panel
        position="top-left"
        className="m-4 mt-20! ml-[288px]! w-64 bg-panel rounded-xl overflow-hidden flex flex-col max-h-[calc(100%-2rem)]"
      >
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
          className="flex-1 overflow-y-auto p-4 space-y-4"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold">
              {t("nodeTemplates.templates")}
            </h3>
            <Button
              size="icon"
              variant="ghost"
              onClick={onClose}
              className="h-6 w-6"
            >
              <span className="text-lg">&times;</span>
            </Button>
          </div>

          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {!isLoading && (!templates || templates.length === 0) && (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">
                {t("nodeTemplates.noTemplates")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("nodeTemplates.noTemplatesDescription")}
              </p>
            </div>
          )}

          {!isLoading && templates && templates.length > 0 && (
            <div className="space-y-2">
              {templates.map((template) => {
                const nodeConfig =
                  NODE_CONFIG[template.config.type as NodeType];
                const Icon = nodeConfig?.icon;
                const color = nodeConfig?.color || "gray-500";

                return (
                  <div
                    key={template.id}
                    className="flex items-center gap-2 p-2 rounded-lg hover:bg-panel-accent transition-all group"
                  >
                    <div
                      className="flex items-center gap-2 flex-1 min-w-0 cursor-move"
                      draggable
                      onDragStart={(event) => onDragStart(event, template)}
                    >
                      <div
                        className={cn(
                          "p-1 text-white rounded-md shrink-0",
                          `bg-${color}`,
                        )}
                      >
                        {Icon && <Icon size={14} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate">
                          {template.name}
                        </p>
                        {template.description && (
                          <p className="text-[10px] text-muted-foreground truncate">
                            {template.description}
                          </p>
                        )}
                      </div>
                    </div>
                    <Popover
                      open={openPopoverId === template.id}
                      onOpenChange={(open) =>
                        setOpenPopoverId(open ? template.id : null)
                      }
                    >
                      <PopoverTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-48 p-2" align="end">
                        <button
                          onClick={() => handleEditClick(template)}
                          className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-accent transition-colors"
                        >
                          <Pencil className="h-4 w-4" />
                          {t("nodeTemplates.edit")}
                        </button>
                        <button
                          onClick={() => handleDuplicateClick(template)}
                          className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-accent transition-colors"
                        >
                          <Copy className="h-4 w-4" />
                          {t("nodeTemplates.duplicate")}
                        </button>
                        <div className="h-px bg-border my-1" />
                        <button
                          onClick={() => handleDeleteClick(template)}
                          className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-destructive/10 text-destructive transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                          {t("common.delete")}
                        </button>
                      </PopoverContent>
                    </Popover>
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>
      </Panel>

      <Dialog
        open={!!templateToDelete}
        onOpenChange={(open) => !open && setTemplateToDelete(null)}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-destructive">
              {t("nodeTemplates.deleteConfirm")}
            </DialogTitle>
            <DialogDescription>
              {t("nodeTemplates.deleteWarning", {
                name: templateToDelete?.name,
              })}
            </DialogDescription>
          </DialogHeader>

          <div className="flex gap-2 justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => setTemplateToDelete(null)}
              disabled={isDeleting}
              className="gap-2"
            >
              <X className="h-4 w-4" />
              {t("common.cancel")}
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
              className="gap-2"
            >
              {isDeleting && <Loader2 className="h-4 w-4 animate-spin" />}
              <Trash2 className="h-4 w-4" />
              {t("common.delete")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {templateToEdit && (
        <EditTemplateModal
          open={!!templateToEdit}
          onOpenChange={(open) => !open && setTemplateToEdit(null)}
          template={templateToEdit}
        />
      )}

      {templateToDuplicate && currentProjectId && (
        <DuplicateTemplateModal
          open={!!templateToDuplicate}
          onOpenChange={(open) => !open && setTemplateToDuplicate(null)}
          template={templateToDuplicate}
          currentProjectId={currentProjectId}
        />
      )}
    </>
  );
};
