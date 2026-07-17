import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
import {
  NodeType,
  type Workflow,
  type StateVariable,
  type StartNodeConfig,
} from "@/entities/workflow/model/types";
import { AddVariablePopover } from "@/shared/ui";
import { Button } from "@/shared/ui/button";
import { Label } from "@/shared/ui/label";
import { Switch } from "@/shared/ui/switch";
import { Textarea } from "@/shared/ui/textarea";
import { useUpdateWorkflowMutation } from "@/entities/workflow/api/workflow.api";
import { toast } from "sonner";
import { StateVariables } from "../state/stateVariables";
import { useSelector } from "react-redux";
import { selectVariablesByWorkflowId } from "@/entities/workflow/model/variables.slice";
import type { RootState } from "@/app/store/store";
import { Divider } from "@/shared/ui/divider";
import { Variable } from "@/entities/workflow/ui/variable";
import { selectCurrentProjectId } from "@/entities/organization";
import { useGetProjectQuery } from "@/entities/project";

interface StartNodeFormProps {
  nodeId: string;
  config?: StartNodeConfig;
  workflow: Workflow;
  projectId?: string;
}

export const StartNodeForm = ({
  nodeId,
  config,
  workflow,
  projectId,
}: StartNodeFormProps) => {
  const { t } = useTranslation();
  const [updateWorkflow] = useUpdateWorkflowMutation();

  // Конфиг стартовой ноды (первая фраза) сохраняется в data ноды через ReactFlow.
  const handleDataChange = useNodeDataChange(nodeId);
  const [formData, setFormData] = useState<StartNodeConfig>({
    firstPhrase: config?.firstPhrase ?? "",
    acceptVoice: config?.acceptVoice ?? false,
  });

  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  const handleAcceptVoiceChange = (checked: boolean) =>
    setFormData((prev) => ({ ...prev, acceptVoice: checked }));

  // Получаем переменные из Redux store
  const variablesList = useSelector((state: RootState) =>
    selectVariablesByWorkflowId(state, workflow.id)
  );

  // Получаем проектные переменные
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: project } = useGetProjectQuery(currentProjectId!, {
    skip: !currentProjectId,
  });
  const projectVariables = (project?.stateSchema || []) as StateVariable[];

  const handleSaveVariable = async (
    variable: StateVariable,
    index?: number
  ) => {
    let newVariablesList: StateVariable[];

    if (index !== undefined) {
      // Редактирование существующей переменной
      newVariablesList = [...variablesList];
      newVariablesList[index] = variable;
    } else {
      // Добавление новой переменной
      newVariablesList = [...variablesList, variable];
    }

    // Сохраняем на сервер
    const updatedWorkflow = {
      ...workflow,
      state: newVariablesList,
    };

    const response = await updateWorkflow(updatedWorkflow);
    if (response.error) {
      toast.error(
        index !== undefined
          ? t("nodeForms.start.variableUpdateError")
          : t("nodeForms.start.variableAddError")
      );
    } else {
      toast.success(
        index !== undefined
          ? t("nodeForms.start.variableUpdated", { name: variable.name })
          : t("nodeForms.start.variableAdded", { name: variable.name })
      );
      // Переменные автоматически обновятся через variables.slice extraReducers
    }
  };

  const handleUpdateVariable = async (
    variable: StateVariable,
    index: number
  ) => {
    await handleSaveVariable(variable, index);
  };

  const handleDeleteVariable = async (index: number) => {
    const newVariablesList = variablesList.filter((_, i) => i !== index);

    // Сохраняем на сервер
    const updatedWorkflow = {
      ...workflow,
      state: newVariablesList,
    };

    const response = await updateWorkflow(updatedWorkflow);
    if (response.error) {
      toast.error(t("nodeForms.start.variableDeleteError"));
    } else {
      toast.success(t("nodeForms.start.variableDeleted"));
      // Переменные автоматически обновятся через variables.slice extraReducers
    }
  };

  return (
    <BaseForm nodeType={NodeType.START} label={t("nodeForms.start.title")} projectId={projectId}>
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="start-first-phrase">
            {t("nodeForms.start.firstPhrase")}
          </Label>
          <Textarea
            id="start-first-phrase"
            value={formData.firstPhrase ?? ""}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, firstPhrase: e.target.value }))
            }
            placeholder={t("nodeForms.start.firstPhrasePlaceholder")}
          />
          <p className="text-xs text-muted-foreground">
            {t("nodeForms.start.firstPhraseHint")}
          </p>
        </div>

        <Divider />

        {/* Голосовой ввод: расшифровка входящего аудио в сообщение прогона */}
        <div className="space-y-3">
          <div className="flex justify-between gap-4 items-center">
            <Label htmlFor="start-accept-voice">
              {t("nodeForms.start.acceptVoice")}
            </Label>
            <Switch
              id="start-accept-voice"
              checked={formData.acceptVoice ?? false}
              onCheckedChange={handleAcceptVoiceChange}
              showIcons={false}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {t("nodeForms.start.acceptVoiceHint")}
          </p>
        </div>

        <Divider />

        <div>
          <h4 className="text-sm font-medium mb-4">
            {t("nodeForms.start.inputVariables")}
          </h4>
          <Variable
            variable={{
              name: "input_as_text",
              type: "string",
            }}
          />
        </div>

        {/* Секция проектных переменных */}
        {projectVariables.length > 0 && (
          <>
            <Divider />
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium">
                  {t("nodeForms.start.projectVariables")}
                </h4>
              </div>
              <div className="space-y-3">
                {projectVariables.map((variable, index) => (
                  <Variable key={index} variable={variable} />
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                {t("nodeForms.start.projectVariablesNote")}
              </p>
            </div>
          </>
        )}

        {/* Секция переменных состояния */}
        <Divider />
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium">
              {t("nodeForms.start.stateVariables")}
            </h4>
            <AddVariablePopover
              workflow={workflow}
              onSaveVariable={handleSaveVariable}
              existingVariables={variablesList}
            >
              <Button size="sm" variant="outline">
                {t("nodeForms.start.add")}
              </Button>
            </AddVariablePopover>
          </div>

          {/* Список текущих переменных */}
          <StateVariables
            variables={variablesList}
            workflow={workflow}
            onUpdateVariable={handleUpdateVariable}
            onDeleteVariable={handleDeleteVariable}
          />
        </div>
      </div>
    </BaseForm>
  );
};
