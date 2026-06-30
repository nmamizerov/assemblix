import {
  Bot,
  CircleStop,
  Database,
  GitFork,
  Globe,
  Play,
  Plus,
  Sticker,
} from "lucide-react";
import { NodeType } from "../../../model/types";
import type { LucideProps } from "lucide-react";
import type { ForwardRefExoticComponent, RefAttributes } from "react";
import i18n from "@/shared/i18n";

export interface NodeConfigItem {
  type: NodeType;
  labelKey: string;
  icon: ForwardRefExoticComponent<LucideProps & RefAttributes<SVGSVGElement>>;
  color: string;
  categoryKey: string;
  isSidebarVisible: boolean;
  descriptionKey?: string;
}

// Функция для получения конфигурации с переводами
export const getNodeConfig = (): Record<
  NodeType,
  NodeConfigItem & { label: string; category: string; description?: string }
> => {
  const t = i18n.t.bind(i18n);

  return {
    [NodeType.START]: {
      type: NodeType.START,
      labelKey: "workflow.nodes.start",
      label: t("workflow.nodes.start"),
      icon: Play,
      color: "node-start",
      categoryKey: "workflow.categories.main",
      category: t("workflow.categories.main"),
      isSidebarVisible: false,
      descriptionKey: "workflow.nodeDescriptions.start",
      description: t("workflow.nodeDescriptions.start"),
    },
    [NodeType.AGENT]: {
      type: NodeType.AGENT,
      labelKey: "workflow.nodes.agent",
      label: t("workflow.nodes.agent"),
      icon: Bot,
      color: "node-llm",
      categoryKey: "workflow.categories.main",
      category: t("workflow.categories.main"),
      isSidebarVisible: true,
      descriptionKey: "workflow.nodeDescriptions.agent",
      description: t("workflow.nodeDescriptions.agent"),
    },
    [NodeType.STICKER]: {
      type: NodeType.STICKER,
      labelKey: "workflow.nodes.sticker",
      label: t("workflow.nodes.sticker"),
      icon: Sticker,
      color: "node-sticker",
      categoryKey: "workflow.categories.main",
      category: t("workflow.categories.main"),
      isSidebarVisible: true,
      descriptionKey: "workflow.nodeDescriptions.sticker",
      description: t("workflow.nodeDescriptions.sticker"),
    },
    [NodeType.CONDITION]: {
      type: NodeType.CONDITION,
      labelKey: "workflow.nodes.condition",
      label: t("workflow.nodes.condition"),
      icon: GitFork,
      color: "node-logic",
      categoryKey: "workflow.categories.logic",
      category: t("workflow.categories.logic"),
      isSidebarVisible: true,
      descriptionKey: "workflow.nodeDescriptions.condition",
      description: t("workflow.nodeDescriptions.condition"),
    },
    [NodeType.SET_VARIABLE]: {
      type: NodeType.SET_VARIABLE,
      labelKey: "workflow.nodes.setVariable",
      label: t("workflow.nodes.setVariable"),
      icon: Database,
      color: "node-data",
      categoryKey: "workflow.categories.data",
      category: t("workflow.categories.data"),
      isSidebarVisible: true,
      descriptionKey: "workflow.nodeDescriptions.setVariable",
      description: t("workflow.nodeDescriptions.setVariable"),
    },
    [NodeType.END]: {
      type: NodeType.END,
      labelKey: "workflow.nodes.end",
      label: t("workflow.nodes.end"),
      icon: CircleStop,
      color: "node-tool",
      categoryKey: "workflow.categories.main",
      category: t("workflow.categories.main"),
      isSidebarVisible: true,
      descriptionKey: "workflow.nodeDescriptions.end",
      description: t("workflow.nodeDescriptions.end"),
    },
    [NodeType.HTTP_REQUEST]: {
      type: NodeType.HTTP_REQUEST,
      labelKey: "workflow.nodes.httpRequest",
      label: t("workflow.nodes.httpRequest"),
      icon: Globe,
      color: "node-http",
      categoryKey: "workflow.categories.integrations",
      category: t("workflow.categories.integrations"),
      isSidebarVisible: true,
      descriptionKey: "workflow.nodeDescriptions.httpRequest",
      description: t("workflow.nodeDescriptions.httpRequest"),
    },
    [NodeType.PLACEHOLDER]: {
      type: NodeType.PLACEHOLDER,
      labelKey: "workflow.nodes.newElement",
      label: t("workflow.nodes.newElement"),
      icon: Plus,
      color: "node-placeholder",
      categoryKey: "workflow.categories.main",
      category: t("workflow.categories.main"),
      isSidebarVisible: false,
      descriptionKey: "workflow.nodeDescriptions.newElement",
      description: t("workflow.nodes.newElement"),
    },
  };
};

// Для обратной совместимости
export const NODE_CONFIG = getNodeConfig();

// Node types whose execution-viewer state panel shows a before→after diff.
// All other node types show the full state snapshot instead.
export const STATE_DIFF_NODE_TYPES: NodeType[] = [NodeType.SET_VARIABLE];
