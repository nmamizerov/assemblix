import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { Check, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import { Button } from "@/shared/ui/button";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Variable } from "@/entities/workflow/ui/variable";
import type { StateVariable, Workflow } from "@/entities/workflow/model/types";
import { selectVariablesByWorkflowId } from "@/entities/workflow/model/variables.slice";
import type { RootState } from "@/app/store/store";
import { cn } from "@/shared/lib/utils";
import { selectCurrentProjectId } from "@/entities/organization";
import { useGetProjectQuery } from "@/entities/project";

interface MultiVariableSelectProps {
  workflow: Workflow;
  selectedVariables: string[];
  onSelect: (variables: string[]) => void;
  variableType: "state" | "project";
  placeholder?: string;
}

export const MultiVariableSelect = ({
  workflow,
  selectedVariables,
  onSelect,
  variableType,
  placeholder,
}: MultiVariableSelectProps) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const defaultPlaceholder =
    placeholder || t("nodeForms.end.selectVariables");

  // Получаем переменные в зависимости от типа
  const stateVariables = useSelector((state: RootState) =>
    selectVariablesByWorkflowId(state, workflow.id)
  );

  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: currentProject } = useGetProjectQuery(currentProjectId!, {
    skip: !currentProjectId || variableType !== "project",
  });

  const projectVariables = useMemo<StateVariable[]>(() => {
    if (variableType !== "project" || !currentProject?.stateSchema) return [];
    return currentProject.stateSchema.map((v) => ({
      name: v.name,
      type: v.type,
      defaultValue: v.defaultValue as
        | string
        | number
        | boolean
        | null
        | undefined,
    }));
  }, [variableType, currentProject]);

  const variables = variableType === "state" ? stateVariables : projectVariables;
  const prefix = variableType === "state" ? "state" : "project";

  // Создаем список переменных с префиксами
  const variablesWithPrefix = useMemo(() => {
    return variables.map((v) => ({
      variable: v,
      fullName: `${prefix}.${v.name}`,
    }));
  }, [variables, prefix]);

  const handleToggle = (fullName: string) => {
    if (selectedVariables.includes(fullName)) {
      onSelect(selectedVariables.filter((v) => v !== fullName));
    } else {
      onSelect([...selectedVariables, fullName]);
    }
  };

  const handleRemove = (fullName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(selectedVariables.filter((v) => v !== fullName));
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-start text-left font-normal h-auto py-2"
        >
          {selectedVariables.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {selectedVariables.map((fullName) => {
                const item = variablesWithPrefix.find(
                  (v) => v.fullName === fullName
                );
                if (!item) return null;
                return (
                  <span
                    key={fullName}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs"
                  >
                    <span className="font-mono">{prefix}.</span>
                    <span>{item.variable.name}</span>
                    <button
                      onClick={(e) => handleRemove(fullName, e)}
                      className="hover:bg-primary/20 rounded-sm"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                );
              })}
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
              {variableType === "state"
                ? t("nodeForms.end.stateFilter")
                : t("nodeForms.end.projectFilter")}
            </h4>
            <p className="text-xs text-muted-foreground mt-1">
              {t("nodeForms.end.selectVariables")}
            </p>
          </div>
          <ScrollArea className="h-[300px]">
            <div className="p-2 space-y-1">
              {variablesWithPrefix.length === 0 ? (
                <div className="p-4">
                  <p className="text-xs text-muted-foreground text-center">
                    {t("stateVariables.noAvailableVariables")}
                  </p>
                </div>
              ) : (
                variablesWithPrefix.map((item) => {
                  const isSelected = selectedVariables.includes(item.fullName);
                  return (
                    <button
                      key={item.fullName}
                      onClick={() => handleToggle(item.fullName)}
                      className={cn(
                        "w-full p-2 rounded-md text-left hover:bg-accent transition-colors flex items-center gap-2",
                        isSelected && "bg-accent"
                      )}
                    >
                      <span
                        className={cn(
                          "text-xs font-mono font-medium shrink-0",
                          variableType === "project"
                            ? "text-green-600 dark:text-green-400"
                            : "text-indigo-600 dark:text-indigo-400"
                        )}
                      >
                        {prefix}.
                      </span>
                      <div className="flex-1">
                        <Variable
                          showDefaultValue={false}
                          variable={item.variable}
                        />
                      </div>
                      {isSelected && (
                        <Check className="h-4 w-4 text-primary shrink-0" />
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </div>
      </PopoverContent>
    </Popover>
  );
};
