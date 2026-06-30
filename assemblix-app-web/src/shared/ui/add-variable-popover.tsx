import { useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import type { StateVariable, Workflow } from "@/entities/workflow/model/types";
import { VariableForm, type VariableFormData } from "@/features/variable-form";
import { useGetBillingUsageQuery } from "@/entities/billing";
import { selectCurrentProjectId } from "@/entities/organization";
import {
  useGetProjectQuery,
  useUpdateProjectMutation,
} from "@/entities/project";
import { toast } from "sonner";

interface AddVariablePopoverProps {
  workflow: Workflow;
  onSaveVariable: (variable: StateVariable, index?: number) => void;
  children: React.ReactNode;
  editVariable?: StateVariable;
  editIndex?: number;
  existingVariables?: StateVariable[];
}

export const AddVariablePopover = ({
  workflow,
  onSaveVariable,
  children,
  editVariable,
  editIndex,
  existingVariables,
}: AddVariablePopoverProps) => {
  const { t } = useTranslation();
  const variablesList = existingVariables || workflow.state || [];
  const [open, setOpen] = useState(false);

  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });
  const { data: project } = useGetProjectQuery(currentProjectId!, {
    skip: !currentProjectId,
  });
  const [updateProject, { isLoading: isUpdatingProject }] =
    useUpdateProjectMutation();

  const hasProjectVariablesFeature =
    billingUsage?.features.projectVariables ?? true;

  const initialFormValues: VariableFormData | undefined = editVariable
    ? {
        name: editVariable.name,
        type: editVariable.type as VariableFormData["type"],
        defaultValue: editVariable.defaultValue,
      }
    : undefined;

  const handleSubmit = async (data: VariableFormData) => {
    // Если это проектная переменная, сохраняем через API проекта
    if (data.isProjectVariable && currentProjectId && project) {
      try {
        const newVariable = {
          name: data.name,
          type: data.type,
          defaultValue: data.defaultValue ?? null,
        };
        const stateSchema = project.stateSchema || [];
        await updateProject({
          projectId: currentProjectId,
          data: {
            stateSchema: [...stateSchema, newVariable],
          },
        }).unwrap();
        toast.success(t("projectSettings.variableAdded"));
        setOpen(false);
      } catch (error) {
        console.error(error);
        if (
          error &&
          typeof error === "object" &&
          "status" in error &&
          error.status === 403
        ) {
          const errorData = error as {
            status: number;
            data?: { detail?: string };
          };
          toast.error(
            errorData.data?.detail || t("billing.errors.featureNotAvailable")
          );
        } else {
          toast.error(t("projectSettings.addError"));
        }
      }
    } else {
      // Обычная переменная воркфлоу
      onSaveVariable(data as StateVariable, editIndex);
      setOpen(false);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent className="w-[400px]" align="start">
        <VariableForm
          initialValues={initialFormValues}
          existingNames={variablesList.map((v) => v.name)}
          onSubmit={handleSubmit}
          showProjectVariableCheckbox={true}
          hasProjectVariablesFeature={hasProjectVariablesFeature}
          isLoading={isUpdatingProject}
        />
      </PopoverContent>
    </Popover>
  );
};
