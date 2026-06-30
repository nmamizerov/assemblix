import { Input } from "@/shared/ui/input";
import { Checkbox } from "@/shared/ui/checkbox";
import { Label } from "@/shared/ui/label";
import { cn } from "@/shared/lib/utils";

interface NestedValueEditorProps {
  value: unknown;
  onChange: (value: unknown) => void;
  readOnly?: boolean;
  depth?: number;
  /** Стабильный id для htmlFor / Checkbox id */
  fieldId: string;
}

const isPlainObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

export const NestedValueEditor = ({
  value,
  onChange,
  readOnly = false,
  depth = 0,
  fieldId,
}: NestedValueEditorProps) => {
  if (value === null || value === undefined) {
    return (
      <Input
        type="text"
        value="null"
        disabled
        className="text-xs italic text-muted-foreground"
      />
    );
  }

  if (typeof value === "boolean") {
    return (
      <div className="flex items-center space-x-2">
        <Checkbox
          checked={value}
          onCheckedChange={(checked) => onChange(Boolean(checked))}
          disabled={readOnly}
          id={fieldId}
        />
        <Label htmlFor={fieldId} className="text-xs cursor-pointer">
          {value ? "true" : "false"}
        </Label>
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <Input
        type="number"
        value={value}
        onChange={(e) => {
          const num = parseFloat(e.target.value);
          onChange(isNaN(num) ? 0 : num);
        }}
        disabled={readOnly}
        className="text-xs"
      />
    );
  }

  if (typeof value === "string") {
    return (
      <Input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={readOnly}
        className="text-xs"
      />
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <p className="text-xs italic text-muted-foreground py-1">[ ] empty</p>
      );
    }
    return (
      <div
        className={cn(
          "space-y-2 border-l-2 border-border/60 pl-3",
          depth === 0 && "ml-0",
        )}
      >
        {value.map((item, index) => (
          <div key={index} className="space-y-1">
            <span className="text-[10px] font-mono text-muted-foreground">
              [{index}]
            </span>
            <NestedValueEditor
              value={item}
              onChange={(next) => {
                const copy = [...value];
                copy[index] = next;
                onChange(copy);
              }}
              readOnly={readOnly}
              depth={depth + 1}
              fieldId={`${fieldId}-${index}`}
            />
          </div>
        ))}
      </div>
    );
  }

  if (isPlainObject(value)) {
    const keys = Object.keys(value);
    if (keys.length === 0) {
      return (
        <p className="text-xs italic text-muted-foreground py-1">{"{ }"} empty</p>
      );
    }
    return (
      <div
        className={cn(
          "space-y-2 border-l-2 border-border/60 pl-3",
          depth === 0 && "ml-0",
        )}
      >
        {keys.map((key) => (
          <div key={key} className="space-y-1">
            <Label className="text-xs font-medium text-muted-foreground">
              {key}
            </Label>
            <NestedValueEditor
              value={value[key]}
              onChange={(next) => onChange({ ...value, [key]: next })}
              readOnly={readOnly}
              depth={depth + 1}
              fieldId={`${fieldId}-${key}`}
            />
          </div>
        ))}
      </div>
    );
  }

  // Неизвестный тип — показываем как строку без редактирования
  return (
    <Input
      type="text"
      value={String(value)}
      disabled
      className="text-xs italic text-muted-foreground"
    />
  );
};
