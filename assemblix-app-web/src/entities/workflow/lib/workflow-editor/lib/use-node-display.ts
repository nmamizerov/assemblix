import { Zap, type LucideIcon } from "lucide-react";
import { useGetNodesQuery } from "@/entities/workflow";
import { NODE_CONFIG } from "../model/config";
import { iconByName } from "../ui/nodes/icon-by-name";

export interface NodeDisplay {
  Icon: LucideIcon;
  label: string;
  color: string;
}

/**
 * Resolves visual metadata (icon, label, color) for a node type, covering both
 * built-in types (NODE_CONFIG) and descriptor-driven custom nodes (e.g. `delay`)
 * fetched via useGetNodesQuery. Mirrors GenericNode's resolution so debug and
 * execution-viewer panels render custom nodes instead of falling through blank.
 */
export const useNodeDisplay = (nodeType: string): NodeDisplay => {
  const { data: descriptors } = useGetNodesQuery();

  const builtin = (
    NODE_CONFIG as Record<string, { icon: LucideIcon; label: string; color: string } | undefined>
  )[nodeType];
  if (builtin) {
    return { Icon: builtin.icon, label: builtin.label, color: builtin.color };
  }

  const descriptor = descriptors?.find((d) => d.type === nodeType);
  if (descriptor) {
    return {
      Icon: iconByName[descriptor.icon] ?? Zap,
      label: descriptor.displayName,
      color: descriptor.color,
    };
  }

  return { Icon: Zap, label: nodeType, color: "node-llm" };
};
