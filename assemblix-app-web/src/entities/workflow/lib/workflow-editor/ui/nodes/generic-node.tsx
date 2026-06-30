import { memo } from "react";
import type { NodeProps } from "@xyflow/react";
import { Position } from "@xyflow/react";
import { Zap, type LucideIcon } from "lucide-react";
import { BaseNode, type BaseNodeProps } from "./base-node";
import { useGetNodesQuery } from "@/entities/workflow";
import { iconByName } from "./icon-by-name";

type HandleDef = NonNullable<BaseNodeProps["handles"]>[number];

/**
 * Generic canvas node component for descriptor-driven node types (e.g. `delay`).
 * ReactFlow renders this for any node type not registered with a bespoke component.
 *
 * Visual metadata (label, icon, color) is resolved at render time from the
 * NodeDescriptor fetched via useGetNodesQuery — same data as the sidebar uses.
 * If descriptors haven't loaded yet, falls back to the node type string.
 */
export const GenericNode = memo(({ id, type, selected }: NodeProps) => {
  const { data: descriptors } = useGetNodesQuery();
  const descriptor = descriptors?.find((d) => d.type === type);

  const IconComponent: LucideIcon = descriptor?.icon
    ? (iconByName[descriptor.icon] ?? Zap)
    : Zap;
  const label = descriptor?.displayName ?? type ?? id;
  const color = descriptor?.color ?? "node-llm";
  const isTerminal = Boolean(descriptor?.isTerminal);
  const branching = Boolean(descriptor?.branching);

  const handles: HandleDef[] = [];

  if (branching) {
    // branching nodes: one target on left, two sources on right (true/false)
    handles.push({ type: "target", position: Position.Left });
    handles.push({ type: "source", position: Position.Right, index: 0 });
    handles.push({ type: "source", position: Position.Right, index: 1 });
  } else {
    // Standard linear node: target on left, source on right unless terminal
    handles.push({ type: "target", position: Position.Left });
    if (!isTerminal) {
      handles.push({ type: "source", position: Position.Right });
    }
  }

  return (
    <BaseNode
      nodeId={id}
      label={label}
      icon={<IconComponent size={16} />}
      color={color}
      selected={selected}
      handles={handles}
    />
  );
});
