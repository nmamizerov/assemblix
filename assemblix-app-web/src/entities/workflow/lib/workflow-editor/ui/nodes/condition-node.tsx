import { memo } from "react";
import { useTranslation } from "react-i18next";
import type { Node, NodeProps } from "@xyflow/react";
import { Position } from "@xyflow/react";
import { BaseNode } from "./base-node";
import { NODE_CONFIG } from "../../model/config";
import { NodeType, type ConditionNodeConfig } from "../../../../model/types";

export const ConditionNode = memo(
  ({
    id,
    selected,
    data,
  }: NodeProps<Node<ConditionNodeConfig, NodeType.CONDITION>>) => {
    const { t } = useTranslation();
    const config = NODE_CONFIG[NodeType.CONDITION];

    const sourceHandlers = data.conditions.map((_, index) => {
      return {
        type: "source" as const,
        position: Position.Right,
        style: { top: `${70 + index * 36}px` },
        index: index,
      };
    });
    return (
      <BaseNode
        nodeId={id}
        label={config.label}
        icon={<config.icon size={16} />}
        color={config.color}
        selected={selected}
        handles={[
          { type: "target", position: Position.Left },
          ...sourceHandlers,
          {
            type: "source",
            position: Position.Right,
            style: { top: `${70 + data.conditions.length * 36}px` },
            index: data.conditions.length,
          },
        ]}
      >
        <div className="flex flex-col gap-2 mt-3">
          {data.conditions.map((condition, index) => (
            <div
              key={index}
              className="bg-muted px-2 h-7 flex items-center  rounded-md p-1 text-xs max-w-[250px]"
            >
              <div className="truncate">
                {condition.name || condition.expression}
              </div>
            </div>
          ))}
          <div className="bg-muted px-2 h-7 flex items-center  rounded-md p-1 text-xs max-w-[250px]">
            <div className="truncate">{t("nodes.condition.else")}</div>
          </div>
        </div>
      </BaseNode>
    );
  }
);
