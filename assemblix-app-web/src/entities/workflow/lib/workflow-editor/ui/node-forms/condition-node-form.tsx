import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
import {
  CELTextarea,
  type CELTextareaRef,
  type CELVariableType,
} from "@/shared/ui/cel-input";
import { Label } from "@/shared/ui/label";
import { Button } from "@/shared/ui/button";
import {
  NodeType,
  type ConditionNodeConfig,
  type Condition,
  type Workflow,
} from "../../../../model/types";
import { PlusIcon, TrashIcon } from "lucide-react";
import { CELHelper } from "@/shared/ui";
import { VariableSuggestionsPopover } from "../state/variableSuggestionsPopover";
import { Input } from "@/shared/ui/input";

interface ConditionNodeFormProps {
  nodeId: string;
  config?: ConditionNodeConfig;
  workflow: Workflow;
  projectId?: string;
}

const defaultConfig: ConditionNodeConfig = {
  conditions: [{ name: "", expression: "" }],
};

export const ConditionNodeForm = ({
  nodeId,
  config,
  workflow,
  projectId,
}: ConditionNodeFormProps) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<ConditionNodeConfig>(
    config || defaultConfig
  );
  const [showHelpers, setShowHelpers] = useState<{
    index: number;
    type?: CELVariableType;
    term?: string;
  } | null>(null);
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
    []
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

  const handleConditionChange = (
    index: number,
    field: keyof Condition,
    value: string
  ) => {
    const newConditions = [...formData.conditions];
    newConditions[index] = { ...newConditions[index], [field]: value };
    setFormData((prev) => ({ ...prev, conditions: newConditions }));
  };

  const addCondition = () => {
    const newConditions = [
      ...formData.conditions,
      { expression: "", branch: "", name: "" },
    ];
    setFormData((prev) => ({ ...prev, conditions: newConditions }));
  };

  const removeCondition = (index: number) => {
    const newConditions = formData.conditions.filter((_, i) => i !== index);
    setFormData((prev) => ({ ...prev, conditions: newConditions }));
  };

  return (
    <>
      <BaseForm
        nodeType={NodeType.CONDITION}
        label={t("nodeForms.condition.title")}
        projectId={projectId}
      >
        <div className="space-y-2 max-w-[288px]">
          {/* Условия */}
          <div className="flex items-center justify-between sticky top-0 z-10 bg-panel py-2">
            <Label>{t("nodeForms.condition.conditions")}</Label>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              onClick={addCondition}
            >
              <PlusIcon />
            </Button>
          </div>
          <div className="flex flex-col gap-3">
            {formData.conditions.map((condition, index) => (
              <div key={index} className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">
                    {t("nodeForms.condition.expression", { number: index + 1 })}
                  </Label>
                  {formData.conditions.length > 1 && (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => removeCondition(index)}
                    >
                      <TrashIcon className="size-3" />
                    </Button>
                  )}
                </div>
                <div className="space-y-2">
                  <Input
                    value={condition.name}
                    placeholder={t("nodeForms.condition.namePlaceholder")}
                    onChange={(e) =>
                      handleConditionChange(index, "name", e.target.value)
                    }
                  />
                </div>
                <div
                  ref={(el) => {
                    textareaContainerRefs.current[index] = el;
                  }}
                >
                  <CELTextarea
                    ref={(el) => {
                      textareaRefs.current[index] = el;
                    }}
                    id={`condition-expression-${index}`}
                    className="text-xs placeholder:text-xs"
                    value={condition.expression}
                    onChange={(value) =>
                      handleConditionChange(index, "expression", value)
                    }
                    placeholder={t("nodeForms.condition.expressionPlaceholder")}
                    isHelpersVisible={showHelpers?.index === index}
                    onShowHelpers={(type, term) => {
                      handleShowHelpers(index, type, term);
                    }}
                    onHideHelpers={handleHideHelpers}
                  />
                </div>
                {index === 0 && <CELHelper />}
              </div>
            ))}
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
    </>
  );
};
