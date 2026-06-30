import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNodes } from "@xyflow/react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import {
  NodeType,
  type AgentNodeConfig,
} from "../../model/types";
import {
  AgentListSidebar,
  type AgentListItem,
} from "./AgentListSidebar";
import { AgentInstructionsEditor } from "./AgentInstructionsEditor";

interface BulkInstructionsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export const BulkInstructionsDialog = ({
  open,
  onOpenChange,
}: BulkInstructionsDialogProps) => {
  const { t } = useTranslation();
  const nodes = useNodes();
  const [userSelectedId, setUserSelectedId] = useState<string | null>(null);

  const agentItems = useMemo<AgentListItem[]>(
    () =>
      nodes
        .filter((node) => node.type === NodeType.AGENT)
        .map((node, index) => ({
          id: node.id,
          config: node.data as AgentNodeConfig,
          fallbackName: t("workflow.bulkInstructions.unnamedAgent", {
            index: index + 1,
          }),
        })),
    [nodes, t],
  );

  const selectedAgent = useMemo<AgentListItem | null>(() => {
    if (agentItems.length === 0) return null;
    const userPick = userSelectedId
      ? agentItems.find((agent) => agent.id === userSelectedId)
      : undefined;
    return userPick ?? agentItems[0];
  }, [agentItems, userSelectedId]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setUserSelectedId(null);
    }
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-5xl w-[90vw] h-[80vh] flex flex-col overflow-hidden p-0 gap-0">
        <DialogHeader className="px-4 py-3 border-b">
          <DialogTitle>{t("workflow.bulkInstructions.title")}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-1 overflow-hidden min-h-0">
          {agentItems.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground p-8 text-center">
              {t("workflow.bulkInstructions.emptyState")}
            </div>
          ) : (
            <>
              <AgentListSidebar
                agents={agentItems}
                selectedId={selectedAgent?.id ?? null}
                onSelect={setUserSelectedId}
              />
              {selectedAgent && (
                <AgentInstructionsEditor
                  key={selectedAgent.id}
                  nodeId={selectedAgent.id}
                  agentName={
                    selectedAgent.config.name?.trim() ||
                    selectedAgent.fallbackName
                  }
                  config={selectedAgent.config}
                />
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
