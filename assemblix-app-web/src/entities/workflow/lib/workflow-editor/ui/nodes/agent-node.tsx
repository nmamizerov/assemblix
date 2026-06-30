import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { Position } from "@xyflow/react";
import { BaseNode } from "./base-node";
import { NODE_CONFIG } from "../../model/config";
import { NodeType, type AgentNodeConfig } from "../../../../model/types";
import { useTranslation } from "react-i18next";
import {
  CREDENTIAL_TYPE_CONFIG,
  getCredentialTypeForProvider,
} from "@/entities/credential";

export const AgentNode = memo(
  ({
    id,
    selected,
    data,
  }: NodeProps<Node<AgentNodeConfig, NodeType.AGENT>>) => {
    const config = NODE_CONFIG[NodeType.AGENT];
    const { t } = useTranslation();

    const warning = !data.model
      ? { message: t("workflow.node.agent.warnings.modelNotSelected") }
      : undefined;

    const credentialType = getCredentialTypeForProvider(data.provider);
    const providerIcon = credentialType
      ? CREDENTIAL_TYPE_CONFIG[credentialType].icon
      : undefined;

    return (
      <BaseNode
        nodeId={id}
        label={data.name}
        sublabel={config.label}
        icon={<config.icon size={16} />}
        color={config.color}
        selected={selected}
        warning={warning}
        handles={[
          { type: "target", position: Position.Left },
          { type: "source", position: Position.Right },
        ]}
      >
        {data.model && (
          <div className="mt-2 flex items-center gap-2">
            {providerIcon && (
              <img
                src={providerIcon}
                alt={data.provider}
                className="h-4 w-4 shrink-0"
              />
            )}
            <span className="text-xs text-muted-foreground">{data.model}</span>
          </div>
        )}
      </BaseNode>
    );
  }
);
