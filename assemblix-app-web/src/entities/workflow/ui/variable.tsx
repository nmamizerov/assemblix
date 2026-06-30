import { useTranslation } from "react-i18next";
import type { StateVariable } from "../model";
import { VARIABLE_TYPE_CONFIG } from "../model/config";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip";

type Props = {
  variable: StateVariable;
  controls?: React.ReactNode;
  showDefaultValue?: boolean;
  prefix?: string;
};

export const Variable = ({
  variable,
  controls,
  showDefaultValue = true,
}: Props) => {
  const { t } = useTranslation();
  const Icon = VARIABLE_TYPE_CONFIG[variable.type].icon;

  const hasDefault =
    variable.defaultValue !== null &&
    variable.defaultValue !== undefined &&
    variable.defaultValue !== "";

  const isObjectValue =
    typeof variable.defaultValue === "object" && variable.defaultValue !== null;
  const objectKeyCount = isObjectValue
    ? Object.keys(variable.defaultValue as Record<string, unknown>).length
    : 0;

  const previewValue = hasDefault
    ? isObjectValue
      ? objectKeyCount === 0
        ? t("variableForm.objectEmpty")
        : t("variableForm.objectSummary", { count: objectKeyCount })
      : typeof variable.defaultValue === "boolean"
        ? variable.defaultValue
          ? "true"
          : "false"
        : String(variable.defaultValue)
    : "";

  const fullValue = hasDefault
    ? isObjectValue
      ? JSON.stringify(variable.defaultValue, null, 2)
      : String(variable.defaultValue)
    : "";

  return (
    <div className="min-w-0 overflow-hidden">
      {/* Первая строка: иконка, название, тип, кнопки */}
      <div className="flex items-center gap-2 min-w-0">
        <Icon
          className={`h-3 w-3 shrink-0 ${VARIABLE_TYPE_CONFIG[variable.type].color}`}
        />
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="font-semibold text-xs min-w-0 flex-1 break-all line-clamp-1 cursor-default">
              {variable.name}
            </span>
          </TooltipTrigger>
          <TooltipContent className="z-10000 max-w-[300px] break-all">
            {variable.name}
          </TooltipContent>
        </Tooltip>
        <span className="text-xs text-muted-foreground capitalize shrink-0">
          {variable.type}
        </span>
        {controls}
      </div>

      {/* Вторая строка: чип со значением по умолчанию */}
      {showDefaultValue && hasDefault && (
        <div className="mt-1 min-w-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex max-w-full items-center gap-1 rounded-md border bg-muted/50 px-2 py-0.5 text-[11px] cursor-default">
                <span className="text-muted-foreground shrink-0">
                  {t("stateVariables.defaultValueLabel")}:
                </span>
                <span className="font-medium break-all line-clamp-2 min-w-0">
                  {previewValue}
                </span>
              </span>
            </TooltipTrigger>
            <TooltipContent className="z-10000 max-w-[320px]">
              <pre className="whitespace-pre-wrap break-all text-xs">
                {fullValue}
              </pre>
            </TooltipContent>
          </Tooltip>
        </div>
      )}
    </div>
  );
};
