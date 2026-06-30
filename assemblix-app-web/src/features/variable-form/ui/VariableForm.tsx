import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Button } from "@/shared/ui/button";
import { Checkbox } from "@/shared/ui/checkbox";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectValue,
  SelectTrigger,
  SelectItem,
} from "@/shared/ui/select";
import {
  ObjectValueEditor,
  type JsonObject,
} from "@/shared/ui/object-value-editor";

import type { VariableFormData, VariableType } from "../model/types";
import { Loader2, Pencil } from "lucide-react";

interface VariableFormProps {
  initialValues?: VariableFormData;
  existingNames?: string[];
  onSubmit: (data: VariableFormData) => void;
  onCancel?: () => void;
  submitLabel?: string;
  isLoading?: boolean;
  showProjectVariableCheckbox?: boolean;
  hasProjectVariablesFeature?: boolean;
}

export const VariableForm = ({
  initialValues,
  existingNames = [],
  onSubmit,
  onCancel,
  submitLabel,
  isLoading = false,
  showProjectVariableCheckbox = false,
  hasProjectVariablesFeature = true,
}: VariableFormProps) => {
  const { t } = useTranslation();
  const isEditMode = initialValues !== undefined;

  const [variableType, setVariableType] = useState<VariableType>(
    (initialValues?.type as VariableType) || "string"
  );
  const [variableName, setVariableName] = useState(initialValues?.name || "");
  const [stringValue, setStringValue] = useState(
    initialValues?.type === "string"
      ? String(initialValues.defaultValue || "")
      : ""
  );
  const [numberValue, setNumberValue] = useState(
    initialValues?.type === "number"
      ? String(initialValues.defaultValue || "")
      : ""
  );
  const [booleanValue, setBooleanValue] = useState(
    initialValues?.type === "boolean"
      ? Boolean(initialValues.defaultValue)
      : false
  );
  const [objectValue, setObjectValue] = useState(
    initialValues?.type === "object"
      ? JSON.stringify(initialValues.defaultValue || {}, null, 2)
      : "{}"
  );
  const [isObjectEditorOpen, setIsObjectEditorOpen] = useState(false);
  const [isProjectVariable, setIsProjectVariable] = useState(false);
  const [error, setError] = useState<string>("");

  const parsedObjectValue = useMemo<JsonObject>(() => {
    if (!objectValue.trim()) return {};
    try {
      const parsed = JSON.parse(objectValue);
      if (
        parsed &&
        typeof parsed === "object" &&
        !Array.isArray(parsed)
      ) {
        return parsed as JsonObject;
      }
    } catch {
      // ignore — invalid JSON is surfaced on save
    }
    return {};
  }, [objectValue]);

  const objectKeyCount = Object.keys(parsedObjectValue).length;

  const validateAndSave = (objectOverride?: JsonObject) => {
    // Валидация имени
    if (!variableName.trim()) {
      setError(t("variableForm.nameRequired"));
      return;
    }

    // Проверка на уникальность имени (пропускаем для редактирования той же переменной)
    const isDuplicate = existingNames.some(
      (name) =>
        name === variableName.trim() &&
        (!isEditMode || name !== initialValues?.name)
    );
    if (isDuplicate) {
      setError(t("variableForm.duplicateName"));
      return;
    }

    // Формируем переменную в зависимости от типа
    let defaultValue: string | number | boolean | Record<string, unknown> | null =
      null;

    switch (variableType) {
      case "string":
        defaultValue = stringValue;
        break;
      case "number":
        defaultValue = numberValue ? parseFloat(numberValue) : null;
        break;
      case "boolean":
        defaultValue = booleanValue;
        break;
      case "object": {
        if (objectOverride !== undefined) {
          defaultValue = objectOverride;
          break;
        }
        if (objectValue.trim()) {
          try {
            const parsed = JSON.parse(objectValue);
            if (
              typeof parsed !== "object" ||
              parsed === null ||
              Array.isArray(parsed)
            ) {
              setError(t("variableForm.objectMustBeObject"));
              return;
            }
            defaultValue = parsed;
          } catch {
            setError(t("variableForm.invalidJson"));
            return;
          }
        }
        break;
      }
    }

    const formData: VariableFormData = {
      name: variableName.trim(),
      type: variableType,
      defaultValue,
      isProjectVariable: showProjectVariableCheckbox
        ? isProjectVariable
        : undefined,
    };

    onSubmit(formData);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Табы для выбора типа */}
      <Tabs
        value={variableType}
        className="flex flex-col gap-4"
        onValueChange={(value) => setVariableType(value as VariableType)}
      >
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="string">String</TabsTrigger>
          <TabsTrigger value="number">Number</TabsTrigger>
          <TabsTrigger value="boolean">Boolean</TabsTrigger>
          <TabsTrigger value="object">Object</TabsTrigger>
        </TabsList>

        {/* Имя переменной - всегда показывается */}
        <div className="space-y-1 pt-2">
          <Label htmlFor="variable-name">{t("variableForm.name")}</Label>
          <Input
            id="variable-name"
            value={variableName}
            onChange={(e) => {
              setVariableName(e.target.value);
              setError("");
            }}
            placeholder={t("variableForm.namePlaceholder")}
          />
        </div>

        {/* String type */}
        <TabsContent value="string" className="space-y-1 mt-0">
          <Label htmlFor="string-value">
            {t("variableForm.defaultValue")}{" "}
            <span className="text-xs text-muted-foreground">
              {t("variableForm.optional")}
            </span>
          </Label>
          <Input
            id="string-value"
            value={stringValue}
            onChange={(e) => setStringValue(e.target.value)}
            placeholder={t("variableForm.stringPlaceholder")}
          />
        </TabsContent>

        {/* Number type */}
        <TabsContent value="number" className="space-y-2 mt-0">
          <Label htmlFor="number-value">
            {t("variableForm.defaultValue")}{" "}
            <span className="text-xs text-muted-foreground">
              {t("variableForm.optional")}
            </span>
          </Label>
          <Input
            id="number-value"
            type="number"
            value={numberValue}
            onChange={(e) => setNumberValue(e.target.value)}
            placeholder={t("variableForm.numberPlaceholder")}
          />
        </TabsContent>

        {/* Boolean type */}
        <TabsContent value="boolean" className="space-y-2 mt-0">
          <div className="space-y-2">
            <Label htmlFor="boolean-value">
              {t("variableForm.defaultValue")}
            </Label>
            <Select
              value={booleanValue.toString()}
              onValueChange={(value) => setBooleanValue(value === "true")}
            >
              <SelectTrigger id="boolean-value">
                <SelectValue
                  placeholder={t("variableForm.booleanPlaceholder")}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true">true</SelectItem>
                <SelectItem value="false">false</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </TabsContent>

        {/* Object type */}
        <TabsContent value="object" className="mt-0">
          <button
            type="button"
            onClick={() => setIsObjectEditorOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-full border bg-muted/50 px-3 py-1 text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="text-muted-foreground">
              {t("variableForm.defaultValue")}:
            </span>
            <span className="font-medium">
              {objectKeyCount === 0
                ? t("variableForm.objectEmpty")
                : t("variableForm.objectSummary", { count: objectKeyCount })}
            </span>
            <Pencil className="size-3 text-muted-foreground" />
          </button>
        </TabsContent>
      </Tabs>

      {/* Галочка "Проектная переменная" */}
      {showProjectVariableCheckbox && !isEditMode && (
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            {hasProjectVariablesFeature ? (
              <>
                <Checkbox
                  id="project-variable"
                  checked={isProjectVariable}
                  onCheckedChange={(checked) =>
                    setIsProjectVariable(checked === true)
                  }
                />
                <div className="grid gap-1.5 leading-none">
                  <Label
                    htmlFor="project-variable"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    {t("variableForm.projectVariable")}
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    {t("variableForm.projectVariableDescription")}
                  </p>
                </div>
              </>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="project-variable" checked={false} disabled />
                    <div className="grid gap-1.5 leading-none">
                      <Label
                        htmlFor="project-variable"
                        className="text-sm font-medium leading-none opacity-50"
                      >
                        {t("variableForm.projectVariable")}
                      </Label>
                      <p className="text-xs text-muted-foreground opacity-50">
                        {t("variableForm.projectVariableDescription")}
                      </p>
                    </div>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t("variableForm.projectVariableUpgradeRequired")}</p>
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>
      )}

      {/* Сообщение об ошибке */}
      {error && <p className="text-xs text-destructive">{error}</p>}

      {/* Кнопки действий */}
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button
            variant="ghost"
            onClick={onCancel}
            disabled={isLoading}
            type="button"
          >
            {t("common.cancel")}
          </Button>
        )}
        <Button
          onClick={() => validateAndSave()}
          disabled={isLoading}
          size={onCancel ? "default" : "sm"}
          className={onCancel ? "" : "ml-auto"}
          type="button"
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {t("common.loading")}
            </>
          ) : (
            submitLabel || (isEditMode ? t("common.update") : t("common.save"))
          )}
        </Button>
      </div>

      <ObjectValueEditor
        open={isObjectEditorOpen}
        initialValue={parsedObjectValue}
        onOpenChange={setIsObjectEditorOpen}
        onSave={(next) => {
          setObjectValue(JSON.stringify(next, null, 2));
          setError("");
          validateAndSave(next);
        }}
      />
    </div>
  );
};
