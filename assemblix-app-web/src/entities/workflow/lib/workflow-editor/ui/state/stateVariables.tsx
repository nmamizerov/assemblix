import { useTranslation } from "react-i18next";
import { Settings, Trash2 } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { AddVariablePopover } from "@/shared/ui";
import type { StateVariable, Workflow } from "@/entities/workflow/model/types";
import { Variable } from "@/entities/workflow/ui/variable";

interface StateVariablesProps {
  variables: StateVariable[];
  workflow: Workflow;
  onUpdateVariable: (variable: StateVariable, index: number) => void;
  onDeleteVariable: (index: number) => void;
}

export const StateVariables = ({
  variables,
  workflow,
  onUpdateVariable,
  onDeleteVariable,
}: StateVariablesProps) => {
  const { t } = useTranslation();

  if (!variables || variables.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("stateVariables.noVariablesText")}
      </p>
    );
  }

  return (
    <div className="space-y-3 max-h-52 overflow-y-auto pr-1">
      {variables.map((variable, index) => {
        return (
          <Variable
            key={index}
            variable={variable}
            controls={
              <>
                <AddVariablePopover
                  workflow={workflow}
                  onSaveVariable={(variable, idx) => {
                    if (idx !== undefined) {
                      onUpdateVariable(variable, idx);
                    }
                  }}
                  editVariable={variable}
                  editIndex={index}
                  existingVariables={variables}
                >
                  <Button size="sm" variant="ghost" className="h-7 w-7 p-0">
                    <Settings className="h-3.5 w-3.5" />
                  </Button>
                </AddVariablePopover>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  onClick={() => onDeleteVariable(index)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </>
            }
          />
        );
      })}
    </div>
  );
};
