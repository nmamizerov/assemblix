import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
import { selectVariablesByWorkflowId } from "@/entities/workflow/model/variables.slice";
import type { RootState } from "@/app/store/store";
import { Label } from "@/shared/ui/label";
import {
  CELTextarea,
  type CELTextareaRef,
  type CELVariableType,
} from "@/shared/ui/cel-input";
import { Button } from "@/shared/ui/button";
import { CELHelper } from "@/shared/ui/cel-helper";
import {
  NodeType,
  type SetVariableNodeConfig,
  type SmartMerge,
  type MergeTarget,
  type MergeOperation,
  type Workflow,
} from "../../../../model/types";
import { PlusIcon, TrashIcon } from "lucide-react";
import { Checkbox } from "@/shared/ui/checkbox";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/shared/ui/select";
import { StateVariableSelect } from "../state/stateVariableSelect";
import { VariableSuggestionsPopover } from "../state/variableSuggestionsPopover";

interface SetVariableNodeFormProps {
  nodeId: string;
  config?: SetVariableNodeConfig;
  workflow: Workflow;
  projectId?: string;
}

const defaultConfig: SetVariableNodeConfig = {
  updates: [{ variableName: "", value: "" }],
  merges: [],
};

const defaultMerge: SmartMerge = {
  source: "",
  target: "state",
  targetKey: "",
  operation: "overwrite",
};

export const SetVariableNodeForm = ({
  nodeId,
  config,
  workflow,
  projectId,
}: SetVariableNodeFormProps) => {
  const { t } = useTranslation();
  const stateVariables = useSelector((state: RootState) =>
    selectVariablesByWorkflowId(state, workflow.id),
  );
  const [formData, setFormData] = useState<SetVariableNodeConfig>(
    config || defaultConfig,
  );
  const [showHelpers, setShowHelpers] = useState<{
    index: number;
    type?: CELVariableType;
    term?: string;
  } | null>(null);
  const [valueStrings, setValueStrings] = useState<string[]>(
    (config?.updates || defaultConfig.updates).map((update) =>
      typeof update.value === "object" && update.value !== null
        ? JSON.stringify(update.value, null, 2)
        : String(update.value),
    ),
  );
  const textareaRefs = useRef<Array<CELTextareaRef | null>>([]);
  const textareaContainerRefs = useRef<Array<HTMLDivElement | null>>([]);
  const handleDataChange = useNodeDataChange(nodeId);

  // Вызываем handleDataChange при каждом изменении formData
  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  // Коллбеки для управления подсказками
  const handleShowHelpers = useCallback(
    (index: number, type?: CELVariableType, term?: string) => {
      setShowHelpers((prev) => {
        // Проверяем, изменилось ли состояние
        if (
          prev?.index === index &&
          prev?.type === type &&
          prev?.term === term
        ) {
          return prev;
        }
        return { index, type, term };
      });
    },
    [],
  );

  const handleHideHelpers = useCallback(() => {
    setShowHelpers((prev) => {
      // Только если подсказки открыты
      if (prev === null) {
        return prev;
      }
      return null;
    });
  }, []);

  const handleVariableNameChange = (index: number, value: string) => {
    const newUpdates = [...formData.updates];
    newUpdates[index] = { ...newUpdates[index], variableName: value };
    setFormData((prev) => ({ ...prev, updates: newUpdates }));
  };

  const handleValueChange = (index: number, value: string) => {
    const newValueStrings = [...valueStrings];
    newValueStrings[index] = value;
    setValueStrings(newValueStrings);

    // Всегда сохраняем как строку - бэкенд сам распарсит CEL выражение
    const newUpdates = [...formData.updates];
    newUpdates[index] = { ...newUpdates[index], value };
    setFormData((prev) => ({ ...prev, updates: newUpdates }));
  };

  const addUpdate = () => {
    const newUpdates = [...formData.updates, { variableName: "", value: "" }];
    setFormData((prev) => ({ ...prev, updates: newUpdates }));
    setValueStrings([...valueStrings, ""]);
  };

  const removeUpdate = (index: number) => {
    const newUpdates = formData.updates.filter((_, i) => i !== index);
    setFormData((prev) => ({ ...prev, updates: newUpdates }));
    const newValueStrings = valueStrings.filter((_, i) => i !== index);
    setValueStrings(newValueStrings);
  };

  // Merge refs
  const mergeTextareaRefs = useRef<Array<CELTextareaRef | null>>([]);
  const mergeTextareaContainerRefs = useRef<Array<HTMLDivElement | null>>([]);

  const [mergeHelpers, setMergeHelpers] = useState<{
    index: number;
    type?: CELVariableType;
    term?: string;
  } | null>(null);

  const handleShowMergeHelpers = useCallback(
    (index: number, type?: CELVariableType, term?: string) => {
      setMergeHelpers((prev) => {
        if (
          prev?.index === index &&
          prev?.type === type &&
          prev?.term === term
        ) {
          return prev;
        }
        return { index, type, term };
      });
    },
    [],
  );

  const handleHideMergeHelpers = useCallback(() => {
    setMergeHelpers((prev) => {
      if (prev === null) {
        return prev;
      }
      return null;
    });
  }, []);

  const handleAdvancedToggle = (checked: boolean) => {
    if (checked) {
      setFormData((prev) => ({
        ...prev,
        merges: [{ ...defaultMerge }],
      }));
    } else {
      setFormData((prev) => ({ ...prev, merges: [] }));
    }
  };

  const handleMergeSourceChange = (index: number, value: string) => {
    const newMerges = [...(formData.merges || [])];
    newMerges[index] = { ...newMerges[index], source: value };
    setFormData((prev) => ({ ...prev, merges: newMerges }));
  };

  const handleMergeTargetKeyChange = (index: number, value: string) => {
    const newMerges = [...(formData.merges || [])];
    newMerges[index] = { ...newMerges[index], targetKey: value };
    setFormData((prev) => ({ ...prev, merges: newMerges }));
  };

  const handleMergeTargetChange = (index: number, value: MergeTarget) => {
    const newMerges = [...(formData.merges || [])];
    newMerges[index] = { ...newMerges[index], target: value };
    setFormData((prev) => ({ ...prev, merges: newMerges }));
  };

  const handleMergeOperationChange = (
    index: number,
    value: MergeOperation,
  ) => {
    const newMerges = [...(formData.merges || [])];
    newMerges[index] = { ...newMerges[index], operation: value };
    setFormData((prev) => ({ ...prev, merges: newMerges }));
  };

  const addMerge = () => {
    const newMerges = [...(formData.merges || []), { ...defaultMerge }];
    setFormData((prev) => ({ ...prev, merges: newMerges }));
  };

  const removeMerge = (index: number) => {
    const newMerges = (formData.merges || []).filter((_, i) => i !== index);
    setFormData((prev) => ({ ...prev, merges: newMerges }));
  };

  const isAdvancedUsage = (formData.merges?.length ?? 0) > 0;

  return (
    <>
      <BaseForm
        nodeType={NodeType.SET_VARIABLE}
        label={t("nodeForms.setVariable.title")}
        projectId={projectId}
      >
        <div className="space-y-4">
          {/* Переменные */}
          <div className="space-y-2">
            <div className="flex items-center justify-between sticky top-0 z-10 bg-panel py-2">
              <Label>{t("nodeForms.setVariable.updates")}</Label>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={addUpdate}
              >
                <PlusIcon />
              </Button>
            </div>
            <div className="flex flex-col gap-3">
              {formData.updates.map((update, index) => (
                <div
                  key={index}
                  className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-3"
                >
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-medium text-muted-foreground">
                      {t("nodeForms.setVariable.variable", {
                        number: index + 1,
                      })}
                    </Label>
                    {formData.updates.length > 1 && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => removeUpdate(index)}
                      >
                        <TrashIcon className="size-3" />
                      </Button>
                    )}
                  </div>

                  <div className="space-y-3">
                    <StateVariableSelect
                      workflow={workflow}
                      selectedVariableName={update.variableName}
                      onSelect={(variableName) =>
                        handleVariableNameChange(index, variableName)
                      }
                      placeholder={t("nodeForms.setVariable.selectVariable")}
                      showProjectVariables={true}
                    />
                    <div
                      ref={(el) => {
                        textareaContainerRefs.current[index] = el;
                      }}
                    >
                      <CELTextarea
                        ref={(el) => {
                          textareaRefs.current[index] = el;
                        }}
                        id={`variable-value-${index}`}
                        className="text-xs placeholder:text-xs"
                        value={valueStrings[index]}
                        onChange={(value) => handleValueChange(index, value)}
                        placeholder={t(
                          "nodeForms.setVariable.valuePlaceholder",
                        )}
                        isHelpersVisible={showHelpers?.index === index}
                        onShowHelpers={(type, term) => {
                          handleShowHelpers(index, type, term);
                        }}
                        onHideHelpers={handleHideHelpers}
                      />
                      <CELHelper />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Advanced usage */}
          <div className="mt-4 space-y-3 border-t pt-4">
            <div className="flex items-center gap-2">
              <Checkbox
                id="advanced-usage"
                checked={isAdvancedUsage}
                onCheckedChange={(checked) =>
                  handleAdvancedToggle(checked === true)
                }
              />
              <Label htmlFor="advanced-usage" className="cursor-pointer">
                {t("nodeForms.setVariable.advancedUsage")}
              </Label>
            </div>

            {isAdvancedUsage && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>{t("nodeForms.setVariable.merges")}</Label>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    onClick={addMerge}
                  >
                    <PlusIcon />
                  </Button>
                </div>
                <div className="flex flex-col gap-3">
                  {(formData.merges || []).map((merge, index) => (
                    <div
                      key={index}
                      className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-3"
                    >
                      <div className="flex items-center justify-between">
                        <Label className="text-xs font-medium text-muted-foreground">
                          {t("nodeForms.setVariable.merge", {
                            number: index + 1,
                          })}
                        </Label>
                        {(formData.merges?.length ?? 0) > 1 && (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => removeMerge(index)}
                          >
                            <TrashIcon className="size-3" />
                          </Button>
                        )}
                      </div>

                      <div className="space-y-3">
                        <div>
                          <Label className="text-xs">
                            {t("nodeForms.setVariable.mergeSource")}
                          </Label>
                          <div
                            ref={(el) => {
                              mergeTextareaContainerRefs.current[index] = el;
                            }}
                          >
                            <CELTextarea
                              ref={(el) => {
                                mergeTextareaRefs.current[index] = el;
                              }}
                              id={`merge-source-${index}`}
                              className="text-xs placeholder:text-xs"
                              value={merge.source}
                              onChange={(value) =>
                                handleMergeSourceChange(index, value)
                              }
                              placeholder={t(
                                "nodeForms.setVariable.mergeSourcePlaceholder",
                              )}
                              isHelpersVisible={
                                mergeHelpers?.index === index
                              }
                              onShowHelpers={(type, term) => {
                                handleShowMergeHelpers(index, type, term);
                              }}
                              onHideHelpers={handleHideMergeHelpers}
                            />
                            <CELHelper />
                          </div>
                        </div>

                        <div>
                          <Label className="text-xs">
                            {t("nodeForms.setVariable.mergeTargetKey")}
                          </Label>
                          <Select
                            value={merge.targetKey || "__all__"}
                            onValueChange={(value) =>
                              handleMergeTargetKeyChange(
                                index,
                                value === "__all__" ? "" : value,
                              )
                            }
                          >
                            <SelectTrigger size="sm" className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__all__">
                                {t(
                                  "nodeForms.setVariable.mergeTargetKeyAll",
                                )}
                              </SelectItem>
                              {stateVariables
                                .filter((v) => v.type === "object")
                                .map((v) => (
                                  <SelectItem key={v.name} value={v.name}>
                                    {v.name}
                                  </SelectItem>
                                ))}
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="flex gap-2">
                          <div className="flex-1">
                            <Label className="text-xs">
                              {t("nodeForms.setVariable.mergeTarget")}
                            </Label>
                            <Select
                              value={merge.target}
                              onValueChange={(value) =>
                                handleMergeTargetChange(
                                  index,
                                  value as MergeTarget,
                                )
                              }
                            >
                              <SelectTrigger size="sm" className="w-full">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="state">
                                  {t(
                                    "nodeForms.setVariable.mergeTargetState",
                                  )}
                                </SelectItem>
                                <SelectItem value="project">
                                  {t(
                                    "nodeForms.setVariable.mergeTargetProject",
                                  )}
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <div className="flex-1">
                            <Label className="text-xs">
                              {t("nodeForms.setVariable.mergeOperation")}
                            </Label>
                            <Select
                              value={merge.operation}
                              onValueChange={(value) =>
                                handleMergeOperationChange(
                                  index,
                                  value as MergeOperation,
                                )
                              }
                            >
                              <SelectTrigger size="sm" className="w-full">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="add">
                                  {t(
                                    "nodeForms.setVariable.mergeOperationAdd",
                                  )}
                                </SelectItem>
                                <SelectItem value="subtract">
                                  {t(
                                    "nodeForms.setVariable.mergeOperationSubtract",
                                  )}
                                </SelectItem>
                                <SelectItem value="overwrite">
                                  {t(
                                    "nodeForms.setVariable.mergeOperationOverwrite",
                                  )}
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </BaseForm>
      {showHelpers && (
        <VariableSuggestionsPopover
          showHelpers={showHelpers}
          workflow={workflow}
          currentNodeId={nodeId}
          getTextareaContainerRef={(index) =>
            textareaContainerRefs.current[index]
          }
          getTextareaRef={(index) => textareaRefs.current[index]}
          onClose={handleHideHelpers}
        />
      )}
      {mergeHelpers && (
        <VariableSuggestionsPopover
          showHelpers={mergeHelpers}
          workflow={workflow}
          currentNodeId={nodeId}
          getTextareaContainerRef={(index) =>
            mergeTextareaContainerRefs.current[index]
          }
          getTextareaRef={(index) => mergeTextareaRefs.current[index]}
          onClose={handleHideMergeHelpers}
        />
      )}
    </>
  );
};
