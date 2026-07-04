import type { NodeType } from "@/entities/workflow/model/types";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Button } from "@/shared/ui/button";
import { NODE_CONFIG } from "../../model/config";
import { TrashIcon, BookmarkIcon } from "lucide-react";
import { useReactFlow, useStore } from "@xyflow/react";
import { useCallback, useState } from "react";
import { SaveAsTemplateModal } from "@/entities/node-template";
import type { NodeTemplateConfig } from "@/entities/node-template";
import { useTranslation } from "react-i18next";

interface BaseFormProps {
  nodeType: NodeType | string;
  children: React.ReactNode;
  label?: string;
  /** Override description (used by GenericNodeForm for plugin/dynamic nodes). */
  description?: string;
  projectId?: string;
}

export const BaseForm = ({ nodeType, children, label, description: descriptionProp, projectId }: BaseFormProps) => {
  const { t } = useTranslation();
  const staticDescription = (NODE_CONFIG as Record<string, { description?: string }>)[nodeType]?.description;
  const description = descriptionProp ?? staticDescription;
  const { setNodes, getNodes } = useReactFlow();
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);

  // Получаем выбранные ноды из стора
  const selectedNodeIds = useStore((state) =>
    Array.from(state.nodeLookup.values())
      .filter((node) => node.selected)
      .map((node) => node.id)
  );

  // Получаем конфигурацию текущей ноды для шаблона
  const getNodeConfig = useCallback((): NodeTemplateConfig | null => {
    const nodes = getNodes();
    const selectedNode = nodes.find((node) => selectedNodeIds.includes(node.id));
    
    if (!selectedNode) return null;

    return {
      id: selectedNode.id,
      type: selectedNode.type || "",
      position: selectedNode.position,
      config: selectedNode.data as Record<string, unknown>,
    };
  }, [getNodes, selectedNodeIds]);

  const handleDeleteNode = useCallback(() => {
    if (selectedNodeIds.length > 0) {
      setNodes((nodes) =>
        nodes.filter((node) => !selectedNodeIds.includes(node.id))
      );
    }
  }, [selectedNodeIds, setNodes]);

  const canDelete = nodeType !== "start";
  const canSaveAsTemplate = nodeType !== "start";

  const nodeConfig = getNodeConfig();

  return (
    <div className="flex flex-col flex-1 min-h-0 relative">
      <div className="p-4 border-b border-border sticky top-0 z-10 bg-panel">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold">{label}</h3>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {projectId && canSaveAsTemplate && (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                onClick={() => setIsTemplateModalOpen(true)}
                title={t("nodeTemplates.saveAsTemplate")}
                className="h-6 w-6"
              >
                <BookmarkIcon className="h-3.5 w-3.5" />
              </Button>
            )}
            {canDelete && (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                onClick={handleDeleteNode}
                className="h-6 w-6 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950 shrink-0"
              >
                <TrashIcon className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      </div>
      {/* Внутренняя обёртка radix-viewport рендерится с display:table, что ломает
          position:sticky у заголовков форм — переопределяем её на display:block.
          Панель тянется по контенту (max-h), поэтому у flex-цепочки нет определённой
          высоты и height:100% вьюпорта Radix не разрешается — из-за этого длинная
          форма не скроллилась. Ограничиваем сам вьюпорт (элемент с overflow:scroll)
          высотой относительно окна: короткие формы растут по контенту, длинные —
          упираются в потолок и скроллятся. */}
      <ScrollArea className="flex-1 min-h-0 [&_[data-slot=scroll-area-viewport]]:max-h-[calc(100vh_-_12rem)] [&_[data-slot=scroll-area-viewport]>div]:block!">
        <div className="p-4">{children}</div>
      </ScrollArea>
      
      {projectId && nodeConfig && canSaveAsTemplate && (
        <SaveAsTemplateModal
          open={isTemplateModalOpen}
          onOpenChange={setIsTemplateModalOpen}
          nodeConfig={nodeConfig}
          projectId={projectId}
        />
      )}
    </div>
  );
};

export type { BaseFormProps };
