import { Input } from "@/shared/ui/input";
import { Checkbox } from "@/shared/ui/checkbox";
import { Label } from "@/shared/ui/label";
import type { StateVariable } from "@/entities/workflow/model/types";
import type { StateSchemaVariable } from "@/entities/project/model/types";
import { NestedValueEditor } from "./nested-value-editor";

interface StateEditorProps {
  variable: StateVariable | StateSchemaVariable;
  value: unknown;
  onChange: (value: unknown) => void;
  readOnly?: boolean;
  showLabel?: boolean;
}

export const StateEditor = ({
  variable,
  value,
  onChange,
  readOnly = false,
  showLabel = true,
}: StateEditorProps) => {
  const renderEditor = () => {
    switch (variable.type) {
      case "string":
        return (
          <Input
            type="text"
            value={(value as string) || ""}
            onChange={(e) => onChange(e.target.value)}
            disabled={readOnly}
            className="text-xs"
          />
        );

      case "number":
        return (
          <Input
            type="number"
            value={(value as number) || 0}
            onChange={(e) => {
              const num = parseFloat(e.target.value);
              onChange(isNaN(num) ? 0 : num);
            }}
            disabled={readOnly}
            className="text-xs"
          />
        );

      case "boolean":
        return (
          <div className="flex items-center space-x-2">
            <Checkbox
              checked={Boolean(value)}
              onCheckedChange={(checked) => onChange(checked)}
              disabled={readOnly}
              id={`checkbox-${variable.name}`}
            />
            <Label
              htmlFor={`checkbox-${variable.name}`}
              className="text-xs cursor-pointer"
            >
              {value ? "true" : "false"}
            </Label>
          </div>
        );

      case "object":
        return (
          <NestedValueEditor
            value={value}
            onChange={onChange}
            readOnly={readOnly}
            fieldId={`obj-${variable.name}`}
          />
        );

      default:
        return (
          <Input
            type="text"
            value={String(value || "")}
            onChange={(e) => onChange(e.target.value)}
            disabled={readOnly}
            className="text-xs"
          />
        );
    }
  };

  return (
    <div className="space-y-2">
      {showLabel && (
        <Label className="text-xs font-medium">{variable.name}</Label>
      )}
      {renderEditor()}
    </div>
  );
};
