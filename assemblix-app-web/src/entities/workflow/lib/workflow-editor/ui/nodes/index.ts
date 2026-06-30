import { NodeType } from "../../../../model/types";
import { StartNode } from "./start-node";
import { AgentNode } from "./agent-node";
import { ConditionNode } from "./condition-node";
import { SetVariableNode } from "./set-variable-node";
import { EndNode } from "./end-node";
import { StickerNode } from "./sticker-node";
import { HTTPRequestNode } from "./http-request-node";
import { PlaceholderNode } from "./placeholder-node";
import { GenericNode } from "./generic-node";
import type { NodeTypes } from "@xyflow/react";

/**
 * nodeTypes map passed to ReactFlow.
 * Returns GenericNode for any type not statically registered — this means
 * newly-shipped plugin/descriptor-driven nodes (e.g. `delay`) are rendered
 * without any manual frontend changes.
 *
 * The Proxy intercepts property reads for unknown keys and returns GenericNode.
 * Cast to NodeTypes satisfies the ReactFlow prop type.
 */
const staticNodeTypes = {
  [NodeType.START]: StartNode,
  [NodeType.AGENT]: AgentNode,
  [NodeType.CONDITION]: ConditionNode,
  [NodeType.SET_VARIABLE]: SetVariableNode,
  [NodeType.END]: EndNode,
  [NodeType.STICKER]: StickerNode,
  [NodeType.HTTP_REQUEST]: HTTPRequestNode,
  [NodeType.PLACEHOLDER]: PlaceholderNode,
};

export const nodeTypes = new Proxy(staticNodeTypes as NodeTypes, {
  get(target, prop: string) {
    return Object.prototype.hasOwnProperty.call(target, prop)
      ? (target as Record<string, unknown>)[prop]
      : GenericNode;
  },
  has() {
    // React Flow checks `prop in nodeTypes` to decide if a type is known.
    // Return true for all strings so Flow never logs "unknown node type".
    return true;
  },
});

export * from "./start-node";
export * from "./agent-node";
export * from "./condition-node";
export * from "./set-variable-node";
export * from "./end-node";
export * from "./base-node";
export * from "./http-request-node";
export * from "./placeholder-node";
export * from "./generic-node";
