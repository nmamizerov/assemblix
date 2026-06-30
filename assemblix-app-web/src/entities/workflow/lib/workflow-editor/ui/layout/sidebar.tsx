import { useMemo } from "react";
import { getNodeConfig } from "../../model/config";
import { NodeType } from "../../../../model/types";
import { Panel } from "@xyflow/react";
import { cn } from "@/shared/lib/utils";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { LayoutTemplate, Zap, type LucideIcon } from "lucide-react";
import { useGetNodesQuery } from "@/entities/workflow";
import { iconByName } from "../nodes/icon-by-name";

/** Descriptor category key (backend, lowercase) → i18n key suffix. */
const CATEGORY_KEY_MAP: Record<string, string> = {
  main: "workflow.categories.main",
  logic: "workflow.categories.logic",
  data: "workflow.categories.data",
  integrations: "workflow.categories.integrations",
  utility: "workflow.categories.data",
};

interface SidebarItem {
  type: string;
  label: string;
  icon: LucideIcon;
  color: string;
  category: string;
  isSidebarVisible: boolean;
}

interface WorkflowEditorSidebarProps {
  isHighlighted?: boolean;
  onNodeTypeSelect?: (nodeType: NodeType | string) => void;
  onTemplatesClick?: () => void;
  isTemplatesPanelOpen?: boolean;
}

export const WorkflowEditorSidebar = ({
  isHighlighted = false,
  onNodeTypeSelect,
  onTemplatesClick,
  isTemplatesPanelOpen = false,
}: WorkflowEditorSidebarProps) => {
  const { t } = useTranslation();

  // Static node config (always present as fallback)
  const NODE_CONFIG = getNodeConfig();

  // Backend descriptors for plugin/dynamic nodes
  const { data: descriptors } = useGetNodesQuery();

  // Build a merged list of sidebar items
  const items = useMemo<SidebarItem[]>(() => {
    // Start with static items
    const staticItems: SidebarItem[] = Object.values(NODE_CONFIG)
      .filter((item) => item.isSidebarVisible)
      .map((item) => ({
        type: item.type,
        label: item.label,
        icon: item.icon as LucideIcon,
        color: item.color,
        category: item.category,
        isSidebarVisible: item.isSidebarVisible,
      }));

    const staticTypes = new Set(staticItems.map((i) => i.type));

    // Add descriptor-only items (plugin/dynamic nodes not in static config)
    const dynamicItems: SidebarItem[] = [];
    if (descriptors) {
      for (const d of descriptors) {
        if (!d.sidebarVisible) continue;
        if (staticTypes.has(d.type)) continue; // already covered by static

        const IconComponent = d.icon ? (iconByName[d.icon] ?? Zap) : Zap;
        const categoryKey = CATEGORY_KEY_MAP[d.category?.toLowerCase()] ?? "workflow.categories.data";
        dynamicItems.push({
          type: d.type,
          label: d.displayName,
          icon: IconComponent,
          color: d.color ?? "node-llm",
          category: t(categoryKey),
          isSidebarVisible: true,
        });
      }
    }

    return [...staticItems, ...dynamicItems];
  }, [NODE_CONFIG, descriptors, t]);

  // Group items by category
  const groups = useMemo(
    () =>
      items.reduce((acc, item) => {
        if (!acc[item.category]) acc[item.category] = [];
        acc[item.category].push(item);
        return acc;
      }, {} as Record<string, SidebarItem[]>),
    [items],
  );

  const categoryOrder = [
    t("workflow.categories.main"),
    t("workflow.categories.logic"),
    t("workflow.categories.data"),
    t("workflow.categories.integrations"),
  ];

  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    if (isHighlighted) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
  };

  const handleItemClick = (nodeType: string) => {
    if (isHighlighted && onNodeTypeSelect) {
      onNodeTypeSelect(nodeType as NodeType);
    }
  };

  return (
    <Panel
      position="top-left"
      className={cn(
        "m-4 mt-20! w-64 bg-panel rounded-xl overflow-hidden flex flex-col max-h-[calc(100%-2rem)] transition-all",
        isHighlighted &&
          "ring-4 ring-primary/50 shadow-lg shadow-primary/20 animate-pulse",
      )}
    >
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className="flex-1 overflow-y-auto p-4 pl-2 space-y-6"
        data-tour="sidebar"
      >
        {isHighlighted && (
          <div className="bg-primary/10 border border-primary/30 rounded-lg p-3 mb-4">
            <p className="text-xs font-semibold text-primary">
              {t("workflow.sidebar.selectNodeType")}
            </p>
            <p className="text-[10px] text-muted-foreground mt-1">
              {t("workflow.sidebar.clickToSelect")}
            </p>
          </div>
        )}
        {categoryOrder.map((category) => {
          const categoryItems = groups[category];
          if (!categoryItems) return null;

          return (
            <div key={category}>
              <h3 className="text-[10px] pl-2 font-bold text-muted-foreground uppercase tracking-wider mb-3">
                {category}
              </h3>
              <div className="grid gap-4">
                {categoryItems.map((item) => (
                  <div
                    className={cn(
                      "flex cursor-pointer transition-all hover:bg-panel-accent p-2 rounded-lg text-sm items-center gap-2",
                      isHighlighted &&
                        "hover:scale-105 hover:shadow-md hover:bg-primary/10 hover:ring-2 hover:ring-primary/50",
                    )}
                    key={item.type}
                    onDragStart={(event) => onDragStart(event, item.type)}
                    onClick={() => handleItemClick(item.type)}
                    draggable={!isHighlighted}
                    data-tour={
                      item.type === NodeType.AGENT ? "agent-node" : undefined
                    }
                  >
                    <div
                      className={cn(
                        "p-1 text-white rounded-md",
                        `bg-${item.color}`,
                      )}
                    >
                      <item.icon size={16} />
                    </div>
                    {item.label}
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {/* Templates tab */}
        <div className="border-t border-border pt-4 mt-4">
          <button
            onClick={onTemplatesClick}
            className={cn(
              "w-full flex items-center gap-2 p-2 rounded-lg text-sm transition-colors",
              isTemplatesPanelOpen
                ? "bg-primary/10 text-primary"
                : "hover:bg-panel-accent",
            )}
          >
            <LayoutTemplate className="h-4 w-4" />
            {t("nodeTemplates.templates")}
          </button>
        </div>
      </motion.div>
    </Panel>
  );
};
