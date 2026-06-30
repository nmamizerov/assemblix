import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ExternalLink } from "lucide-react";
import { useReactFlow, useNodes } from "@xyflow/react";
import type { Node as ReactFlowNode } from "@xyflow/react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Button } from "@/shared/ui/button";
import { Label } from "@/shared/ui/label";
import { NodeType, type Workflow, type AgentNodeConfig } from "@/entities/workflow/model/types";

interface AgentNodeSelectProps {
  workflow: Workflow;
  selectedNodeId?: string;
  onSelect: (nodeId: string) => void;
  placeholder?: string;
}

export const AgentNodeSelect = ({
  // workflow не используется, т.к. берем актуальные ноды из useNodes()
  selectedNodeId,
  onSelect,
  placeholder,
}: AgentNodeSelectProps) => {
  const { t } = useTranslation();
  const { setCenter, getNode, setNodes } = useReactFlow();
  const reactFlowNodes = useNodes();

  // Фильтруем только агентские ноды из актуального состояния React Flow
  const agentNodes = useMemo(() => {
    return reactFlowNodes.filter((node) => node.type === NodeType.AGENT) as ReactFlowNode<AgentNodeConfig>[];
  }, [reactFlowNodes]);

  const handleNavigateToNode = () => {
    if (!selectedNodeId) return;
    
    const node = getNode(selectedNodeId);
    if (!node) return;

    // Выделяем ноду
    setNodes((nodes) =>
      nodes.map((n) => ({
        ...n,
        selected: n.id === selectedNodeId,
      }))
    );

    // Перемещаем камеру к ноде с анимацией
    setCenter(node.position.x + 100, node.position.y + 50, {
      zoom: 1.2,
      duration: 800,
    });
  };

  return (
    <div className="space-y-2">
      <Label className="text-xs">{t("nodeForms.end.agentLabel")}</Label>
      <div className="flex gap-2">
        <Select value={selectedNodeId || ""} onValueChange={onSelect}>
          <SelectTrigger className="text-xs">
            <SelectValue placeholder={placeholder || t("nodeForms.end.selectAgent")} />
          </SelectTrigger>
          <SelectContent>
            {agentNodes.length === 0 ? (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                {t("nodeForms.end.noAgents")}
              </div>
            ) : (
              agentNodes.map((node) => (
                <SelectItem key={node.id} value={node.id} className="text-xs">
                  {(node.data as AgentNodeConfig).name || node.id}
                </SelectItem>
              ))
            )}
          </SelectContent>
        </Select>
        {selectedNodeId && (
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={handleNavigateToNode}
            title={t("nodeForms.end.goToAgent")}
            className="shrink-0"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
};
