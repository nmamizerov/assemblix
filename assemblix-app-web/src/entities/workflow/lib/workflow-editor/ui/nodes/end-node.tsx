import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { Position } from "@xyflow/react";
import { BaseNode } from "./base-node";
import { NODE_CONFIG } from "../../model/config";
import { NodeType, type EndNodeConfig } from "../../../../model/types";

export const EndNode = memo(
  ({ id, selected }: NodeProps<Node<EndNodeConfig, NodeType.END>>) => {
    const config = NODE_CONFIG[NodeType.END];
    return (
      <BaseNode
        nodeId={id}
        label={config.label}
        icon={<config.icon size={16} />}
        color={config.color}
        selected={selected}
        handles={[{ type: "target", position: Position.Left }]}
      ></BaseNode>
    );
  }
);
