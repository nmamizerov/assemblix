import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { Label } from "@/shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { CELTextarea } from "@/shared/ui/cel-input";
import { PlusIcon, TrashIcon, Maximize2 } from "lucide-react";
import { Role, type AgentNodeConfig, type Instructions } from "../../model/types";
import { useNodeDataChange } from "../../lib/workflow-editor/ui/node-forms/useNodeDataChange";

interface AgentInstructionsEditorProps {
  nodeId: string;
  agentName: string;
  config: AgentNodeConfig;
}

export const AgentInstructionsEditor = ({
  nodeId,
  agentName,
  config,
}: AgentInstructionsEditorProps) => {
  const { t } = useTranslation();
  const handleDataChange = useNodeDataChange(nodeId);

  const [instructions, setInstructions] = useState<Instructions[]>(
    config.instructions?.length
      ? config.instructions
      : [{ role: Role.USER, content: "" }],
  );
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [expandedValue, setExpandedValue] = useState("");

  useEffect(() => {
    handleDataChange({ ...config, instructions });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instructions]);

  const handleContentChange = (index: number, content: string) => {
    setInstructions((prev) =>
      prev.map((inst, i) => (i === index ? { ...inst, content } : inst)),
    );
  };

  const handleRoleChange = (index: number, role: Role) => {
    setInstructions((prev) =>
      prev.map((inst, i) => (i === index ? { ...inst, role } : inst)),
    );
  };

  const addInstruction = () => {
    setInstructions((prev) => [...prev, { role: Role.USER, content: "" }]);
  };

  const removeInstruction = (index: number) => {
    setInstructions((prev) => prev.filter((_, i) => i !== index));
  };

  const openExpanded = (index: number) => {
    setExpandedIndex(index);
    setExpandedValue(instructions[index]?.content ?? "");
  };

  const handleExpandedSave = () => {
    if (expandedIndex !== null) {
      handleContentChange(expandedIndex, expandedValue);
    }
    setExpandedIndex(null);
  };

  const handleExpandedClose = () => {
    setExpandedIndex(null);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden flex-1 min-w-0">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <h3 className="font-medium text-sm truncate" title={agentName}>
          {agentName}
        </h3>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={addInstruction}
        >
          <PlusIcon className="size-4" />
          {t("workflow.bulkInstructions.addInstruction")}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
        {instructions.map((instruction, index) => (
          <div key={index} className="bg-muted rounded-lg relative">
            {index > 0 && (
              <div className="flex items-center justify-between pr-2">
                <Select
                  value={instruction.role}
                  onValueChange={(value) =>
                    handleRoleChange(index, value as Role)
                  }
                >
                  <SelectTrigger className="border-none shadow-none ring-0! text-xs">
                    <SelectValue
                      placeholder={t("nodeForms.agent.selectRole")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user" className="text-xs">
                      {t("nodeForms.agent.roleUser")}
                    </SelectItem>
                    <SelectItem value="assistant" className="text-xs">
                      {t("nodeForms.agent.roleAssistant")}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="icon-sm"
                  className="size-6"
                  variant="ghost"
                  onClick={() => removeInstruction(index)}
                >
                  <TrashIcon className="size-3" />
                </Button>
              </div>
            )}

            <button
              type="button"
              onClick={() => openExpanded(index)}
              aria-label={t("nodeForms.agent.expandInstruction")}
              className="absolute right-2 bottom-2 z-10 rounded p-1 text-muted-foreground hover:text-foreground hover:bg-background/60 transition-colors"
            >
              <Maximize2 className="h-3 w-3" />
            </button>

            <CELTextarea
              highlightMode="inside-braces"
              disableOtherSuggestions={true}
              className="border-none shadow-none ring-0! min-h-[140px] max-h-[320px]"
              value={instruction.content}
              onChange={(value) => handleContentChange(index, value)}
              placeholder={t("nodeForms.agent.contentPlaceholder")}
            />
          </div>
        ))}
      </div>

      <Dialog
        open={expandedIndex !== null}
        onOpenChange={(open) => !open && handleExpandedClose()}
      >
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>{t("nodeForms.agent.promptModalTitle")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 flex-1 overflow-y-auto">
            <Label htmlFor="bulk-expanded-instruction">
              {t("nodeForms.agent.promptModalLabel")}
            </Label>
            <CELTextarea
              id="bulk-expanded-instruction"
              value={expandedValue}
              onChange={setExpandedValue}
              highlightMode="inside-braces"
              disableOtherSuggestions={true}
              className="border-none shadow-none ring-0! min-h-[320px]"
              placeholder={t("nodeForms.agent.contentPlaceholder")}
            />
          </div>
          <DialogFooter className="shrink-0 border-t pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleExpandedClose}
            >
              {t("nodeForms.agent.cancel")}
            </Button>
            <Button type="button" onClick={handleExpandedSave}>
              {t("nodeForms.agent.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
