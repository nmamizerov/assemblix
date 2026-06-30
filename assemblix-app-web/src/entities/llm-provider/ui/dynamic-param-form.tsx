import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, HelpCircle } from "lucide-react";
import clsx from "clsx";

import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Switch } from "@/shared/ui/switch";
import { Textarea } from "@/shared/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/ui/tooltip";

import { filterVisibleOptions, filterVisibleParams } from "../lib/visibility";
import type { ModelMetadata, ParamDef, ParamOption } from "../model/types";

interface DynamicParamFormProps {
  /** Full parameter schema for the provider — already fetched, no loading state here. */
  paramSchema: ParamDef[];
  /** Currently selected model metadata (drives `show`/`hide` filtering). */
  model: ModelMetadata | undefined;
  /** Current values keyed by `ParamDef.name`. */
  values: Record<string, unknown>;
  /** Patch a single param value. The parent owns the form state. */
  onChange: (name: string, value: unknown) => void;
  /**
   * Optional label for the section heading; if omitted, the form renders
   * inline without a heading.
   */
  heading?: string;
  /** Optional label for the "show advanced" toggle. */
  advancedToggleLabel?: string;
  /**
   * If true, advanced params are always shown — separated by a heading +
   * divider instead of being hidden behind a collapse toggle. Useful when the
   * form already lives in a dedicated surface (modal/drawer) where vertical
   * space isn't tight.
   */
  expandAdvanced?: boolean;
}

/**
 * Renders a form from a backend-driven `ParamDef[]` schema.
 *
 * - Filters fields by the selected model's capabilities (`show`/`hide`).
 * - Splits ordinary and `advanced` params; advanced is collapsed by default.
 * - Falls back to schema defaults when a value is undefined — only on display,
 *   never writes back automatically (keeps the form state minimal).
 */
export const DynamicParamForm = ({
  paramSchema,
  model,
  values,
  onChange,
  heading,
  advancedToggleLabel = "Advanced",
  expandAdvanced = false,
}: DynamicParamFormProps) => {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const visible = useMemo(
    () => filterVisibleParams(paramSchema, model),
    [paramSchema, model],
  );

  const { basic, advanced } = useMemo(() => {
    const basicParams: ParamDef[] = [];
    const advancedParams: ParamDef[] = [];
    for (const param of visible) {
      (param.advanced ? advancedParams : basicParams).push(param);
    }
    return { basic: basicParams, advanced: advancedParams };
  }, [visible]);

  if (visible.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {heading && (
        <Label className="text-sm font-semibold">{heading}</Label>
      )}

      {basic.map((param) => (
        <ParamRow
          key={param.name}
          param={param}
          model={model}
          value={values[param.name]}
          onChange={onChange}
        />
      ))}

      {advanced.length > 0 &&
        (expandAdvanced ? (
          <>
            <div className="flex items-center gap-2 pt-2">
              <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                {advancedToggleLabel}
              </Label>
              <div className="flex-1 h-px bg-border" />
            </div>
            {advanced.map((param) => (
              <ParamRow
                key={param.name}
                param={param}
                model={model}
                value={values[param.name]}
                onChange={onChange}
              />
            ))}
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => setShowAdvanced((prev) => !prev)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showAdvanced ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
              {advancedToggleLabel}
            </button>
            {showAdvanced &&
              advanced.map((param) => (
                <ParamRow
                  key={param.name}
                  param={param}
                  model={model}
                  value={values[param.name]}
                  onChange={onChange}
                />
              ))}
          </>
        ))}
    </div>
  );
};

interface ParamRowProps {
  param: ParamDef;
  model: ModelMetadata | undefined;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
}

const ParamRow = ({ param, model, value, onChange }: ParamRowProps) => {
  const handleChange = (next: unknown) => onChange(param.name, next);
  const fieldId = `dynamic-param-${param.name}`;

  return (
    <div
      className={clsx(
        "flex justify-between gap-4 items-center",
        param.type === "json" && "flex-col items-start gap-1!",
      )}
    >
      <div className="flex items-center gap-1.5 shrink-0">
        <Label htmlFor={fieldId} className="whitespace-nowrap">
          {param.label}
        </Label>
        {param.description && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <HelpCircle className="h-3.5 w-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="max-w-[260px]">
              <p>{param.description}</p>
            </TooltipContent>
          </Tooltip>
        )}
      </div>
      <div className="min-w-0 flex w-full justify-end">
        <ParamInput
          id={fieldId}
          param={param}
          model={model}
          value={value}
          onChange={handleChange}
        />
      </div>
    </div>
  );
};

interface ParamInputProps {
  id: string;
  param: ParamDef;
  model: ModelMetadata | undefined;
  value: unknown;
  onChange: (next: unknown) => void;
}

const ParamInput = ({ id, param, model, value, onChange }: ParamInputProps) => {
  const effectiveValue = value ?? param.default ?? "";

  switch (param.type) {
    case "number":
      return (
        <Input
          id={id}
          type="number"
          value={effectiveValue === "" ? "" : (effectiveValue as number)}
          min={param.min ?? undefined}
          max={param.max ?? undefined}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") {
              onChange(undefined);
              return;
            }
            const parsed = Number(raw);
            onChange(Number.isNaN(parsed) ? undefined : parsed);
          }}
          className="max-w-[200px] text-xs"
        />
      );

    case "boolean":
      return (
        <Switch
          id={id}
          checked={Boolean(value ?? param.default ?? false)}
          onCheckedChange={onChange}
        />
      );

    case "select":
      return (
        <Select
          value={(value ?? param.default ?? "") as string}
          onValueChange={onChange}
        >
          <SelectTrigger
            id={id}
            className="border-none shadow-none ring-0! text-xs max-w-[200px]"
          >
            <SelectValue placeholder={param.label} />
          </SelectTrigger>
          <SelectContent>
            {filterVisibleOptions(param.options, model).map(
              (option: ParamOption) => (
                <SelectItem
                  key={String(option.value)}
                  value={String(option.value)}
                  className="text-xs"
                >
                  {option.label}
                </SelectItem>
              ),
            )}
          </SelectContent>
        </Select>
      );

    case "json":
      return (
        <Textarea
          id={id}
          value={
            typeof value === "string"
              ? value
              : value == null
                ? ""
                : JSON.stringify(value, null, 2)
          }
          rows={4}
          onChange={(e) => onChange(e.target.value)}
          className="border-none shadow-none ring-0! text-xs font-mono"
        />
      );

    case "string":
    default:
      return (
        <Input
          id={id}
          type="text"
          value={(effectiveValue as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="max-w-[200px] text-xs"
        />
      );
  }
};
