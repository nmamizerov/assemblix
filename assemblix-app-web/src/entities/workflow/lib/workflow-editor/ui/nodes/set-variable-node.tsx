import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { Position } from "@xyflow/react";
import { BaseNode } from "./base-node";
import { NODE_CONFIG } from "../../model/config";
import { NodeType, type SetVariableNodeConfig } from "../../../../model/types";

export const SetVariableNode = memo(
  ({
    id,
    selected,
  }: NodeProps<Node<SetVariableNodeConfig, NodeType.SET_VARIABLE>>) => {
    const config = NODE_CONFIG[NodeType.SET_VARIABLE];
    return (
      <BaseNode
        nodeId={id}
        label={config.label}
        icon={<config.icon size={16} />}
        color={config.color}
        selected={selected}
        handles={[
          { type: "target", position: Position.Left, id: "in" },
          { type: "source", position: Position.Right, id: "out" },
        ]}
      ></BaseNode>
    );
  }
);
