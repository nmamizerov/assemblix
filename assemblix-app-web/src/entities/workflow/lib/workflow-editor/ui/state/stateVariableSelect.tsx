import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { Check, Plus } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import { Button } from "@/shared/ui/button";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { AddVariablePopover } from "@/shared/ui/add-variable-popover";
import type { StateVariable, Workflow } from "@/entities/workflow/model/types";
import { VARIABLE_TYPE_CONFIG } from "@/entities/workflow/model/config";
import { selectVariablesByWorkflowId } from "@/entities/workflow/model/variables.slice";
import { useUpdateWorkflowMutation } from "@/entities/workflow/api/workflow.api";
import type { RootState } from "@/app/store/store";
import { cn } from "@/shared/lib/utils";
import { selectCurrentProjectId } from "@/entities/organization";
import { useGetProjectQuery } from "@/entities/project";

interface StateVariableSelectProps {
  workflow: Workflow;
  selectedVariableName?: string;
  onSelect: (variableName: string) => void;
  placeholder?: string;
  showProjectVariables?: boolean;
}

type FieldType = StateVariable["type"];

interface FlatField {
  fullName: string;
  type: FieldType;
  prefix: "state" | "project";
}

const inferType = (value: unknown): FieldType => {
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return "object";
  }
  return "string";
};

const flattenObjectFields = (
  value: unknown,
  parentPath: string,
  prefix: "state" | "project",
): FlatField[] => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return [];
  }
  const fields: FlatField[] = [];
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    const fullName = `${parentPath}.${key}`;
    const childType = inferType(child);
    fields.push({ fullName, type: childType, prefix });
    if (childType === "object") {
      fields.push(...flattenObjectFields(child, fullName, prefix));
    }
  }
  return fields;
};

export const StateVariableSelect = ({
  workflow,
  selectedVariableName,
  onSelect,
  placeholder,
  showProjectVariables = false,
}: StateVariableSelectProps) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [updateWorkflow] = useUpdateWorkflowMutation();
  const defaultPlaceholder =
    placeholder || t("stateVariables.selectPlaceholder");

  const stateVariables = useSelector((state: RootState) =>
    selectVariablesByWorkflowId(state, workflow.id),
  );

  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: currentProject } = useGetProjectQuery(currentProjectId!, {
    skip: !currentProjectId || !showProjectVariables,
  });

  const projectVariables = useMemo<StateVariable[]>(() => {
    if (!showProjectVariables || !currentProject?.stateSchema) return [];
    return currentProject.stateSchema.map((v) => ({
      name: v.name,
      type: v.type,
      defaultValue: v.defaultValue as StateVariable["defaultValue"],
    }));
  }, [showProjectVariables, currentProject]);

  const flatFields = useMemo<FlatField[]>(() => {
    const result: FlatField[] = [];
    const collect = (variables: StateVariable[], prefix: "state" | "project") => {
      variables.forEach((v) => {
        const fullName = `${prefix}.${v.name}`;
        result.push({ fullName, type: v.type, prefix });
        if (v.type === "object") {
          result.push(...flattenObjectFields(v.defaultValue, fullName, prefix));
        }
      });
    };
    collect(stateVariables, "state");
    if (showProjectVariables) {
      collect(projectVariables, "project");
    }
    return result;
  }, [stateVariables, projectVariables, showProjectVariables]);

  const selectedItem = flatFields.find((f) => f.fullName === selectedVariableName);

  const handleSelect = (fullName: string) => {
    onSelect(fullName);
    setOpen(false);
  };

  const handleAddVariable = async (variable: StateVariable) => {
    const updatedState = [...stateVariables, variable];
    await updateWorkflow({
      ...workflow,
      state: updatedState,
    });
    onSelect(`state.${variable.name}`);
  };

  const renderFieldRow = (field: FlatField, isSelected: boolean) => {
    const Icon = VARIABLE_TYPE_CONFIG[field.type].icon;
    const iconColor = VARIABLE_TYPE_CONFIG[field.type].color;
    const path = field.fullName.slice(field.prefix.length + 1);
    return (
      <button
        key={`${field.prefix}-${field.fullName}`}
        onClick={() => handleSelect(field.fullName)}
        className={cn(
          "w-full p-2 rounded-md text-left hover:bg-accent transition-colors flex items-start gap-2",
          isSelected && "bg-accent",
        )}
      >
        <span
          className={cn(
            "text-xs font-mono font-medium shrink-0 mt-0.5",
            field.prefix === "project"
              ? "text-green-600 dark:text-green-400"
              : "text-indigo-600 dark:text-indigo-400",
          )}
        >
          {field.prefix}.
        </span>
        <Icon className={cn("h-3 w-3 shrink-0 mt-1", iconColor)} />
        <span className="flex-1 min-w-0 text-xs font-semibold break-all whitespace-normal">
          {path}
        </span>
        <span className="text-xs text-muted-foreground capitalize shrink-0 mt-0.5">
          {field.type}
        </span>
        {isSelected && <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />}
      </button>
    );
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-start text-left font-normal h-auto min-h-9 py-2 overflow-hidden"
        >
          {selectedItem ? (
            <div className="flex items-start gap-2 min-w-0 w-full">
              <span
                className={cn(
                  "text-xs font-mono font-medium shrink-0 mt-0.5",
                  selectedItem.prefix === "project"
                    ? "text-green-600 dark:text-green-400"
                    : "text-indigo-600 dark:text-indigo-400",
                )}
              >
                {selectedItem.prefix}.
              </span>
              <span className="text-xs font-semibold break-all whitespace-normal min-w-0 flex-1">
                {selectedItem.fullName.slice(selectedItem.prefix.length + 1)}
              </span>
              <span className="text-xs text-muted-foreground capitalize shrink-0 mt-0.5">
                {selectedItem.type}
              </span>
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">
              {defaultPlaceholder}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <div className="flex flex-col">
          <div className="border-b p-3">
            <h4 className="text-sm font-semibold">
              {t("stateVariables.selectTitle")}
            </h4>
            <p className="text-xs text-muted-foreground mt-1">
              {t("stateVariables.selectDescription")}
            </p>
          </div>
          <ScrollArea className="h-[300px]">
            <div className="p-2 space-y-1">
              {flatFields.length === 0 ? (
                <div className="p-4">
                  <p className="text-xs text-muted-foreground text-center">
                    {t("stateVariables.noAvailableVariables")}
                  </p>
                </div>
              ) : (
                (["state", "project"] as const).map((prefix) => {
                  const prefixFields = flatFields.filter(
                    (f) => f.prefix === prefix,
                  );
                  if (prefixFields.length === 0) return null;
                  return (
                    <div key={prefix} className="mb-2">
                      <div className="px-2 pb-1">
                        <h4 className="text-xs font-semibold text-muted-foreground capitalize">
                          {prefix === "state"
                            ? t("availableVariables.groups.state")
                            : t("availableVariables.groups.project")}
                        </h4>
                      </div>
                      {prefixFields.map((field) =>
                        renderFieldRow(
                          field,
                          field.fullName === selectedVariableName,
                        ),
                      )}
                    </div>
                  );
                })
              )}

              <AddVariablePopover
                workflow={workflow}
                onSaveVariable={handleAddVariable}
                existingVariables={stateVariables}
              >
                <button
                  className="w-full p-2 rounded-md text-left hover:bg-accent transition-colors flex items-center gap-2 border border-dashed border-muted-foreground/30 mt-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Plus className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    {t("stateVariables.addVariable")}
                  </span>
                </button>
              </AddVariablePopover>
            </div>
          </ScrollArea>
        </div>
      </PopoverContent>
    </Popover>
  );
};
