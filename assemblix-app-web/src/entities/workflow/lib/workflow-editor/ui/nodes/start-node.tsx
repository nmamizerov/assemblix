import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { Position } from "@xyflow/react";
import { BaseNode } from "./base-node";
import { NODE_CONFIG } from "../../model/config";
import { NodeType, type StartNodeConfig } from "../../../../model/types";

export const StartNode = memo(
  ({ id, selected }: NodeProps<Node<StartNodeConfig, NodeType.START>>) => {
    const config = NODE_CONFIG[NodeType.START];
    return (
      <BaseNode
        nodeId={id}
        label={config.label}
        icon={<config.icon size={16} />}
        color={config.color}
        selected={selected}
        handles={[{ type: "source", position: Position.Right, id: "out" }]}
      ></BaseNode>
    );
  }
);
