import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { Position } from "@xyflow/react";
import { BaseNode } from "./base-node";
import { NODE_CONFIG } from "../../model/config";
import { NodeType, type HTTPRequestNodeConfig } from "../../../../model/types";

export const HTTPRequestNode = memo(
  ({
    id,
    selected,
    data,
  }: NodeProps<Node<HTTPRequestNodeConfig, NodeType.HTTP_REQUEST>>) => {
    const config = NODE_CONFIG[NodeType.HTTP_REQUEST];
    const sublabel = data.url
      ? `${data.method} ${data.url.substring(0, 30)}${
          data.url.length > 30 ? "..." : ""
        }`
      : config.label;

    return (
      <BaseNode
        nodeId={id}
        label={data.method || "HTTP"}
        sublabel={sublabel}
        icon={<config.icon size={16} />}
        color={config.color}
        selected={selected}
        handles={[
          { type: "target", position: Position.Left },
          { type: "source", position: Position.Right },
        ]}
      ></BaseNode>
    );
  }
);
