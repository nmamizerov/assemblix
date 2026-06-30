import { useTranslation } from "react-i18next";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { cn } from "@/shared/lib/utils";
import { createEmptyRow } from "./conversions";
import type { PropertyRow, ValueType } from "./types";

interface ObjectConstructorProps {
  rows: PropertyRow[];
  onChange: (rows: PropertyRow[]) => void;
  depth?: number;
}

export const ObjectConstructor = ({
  rows,
  onChange,
  depth = 0,
}: ObjectConstructorProps) => {
  const { t } = useTranslation();

  const updateRow = (id: string, patch: Partial<PropertyRow>) => {
    onChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  const removeRow = (id: string) => {
    onChange(rows.filter((row) => row.id !== id));
  };

  const addRow = () => {
    onChange([...rows, createEmptyRow()]);
  };

  const handleTypeChange = (id: string, nextType: ValueType) => {
    const row = rows.find((r) => r.id === id);
    if (!row) return;
    updateRow(id, {
      type: nextType,
      primitive: nextType === row.type ? row.primitive : "",
      booleanValue: nextType === "boolean" ? row.booleanValue : false,
      children: nextType === "object" ? row.children : [],
    });
  };

  return (
    <div className={cn("flex flex-col gap-2", depth > 0 && "pl-4 border-l")}>
      {rows.length === 0 && (
        <p className="text-xs text-muted-foreground italic py-1">
          {t("objectValueEditor.emptyObject")}
        </p>
      )}

      {rows.map((row) => (
        <div key={row.id} className="flex flex-col gap-2">
          <div className="flex items-start gap-2">
            <Input
              value={row.key}
              onChange={(e) => updateRow(row.id, { key: e.target.value })}
              placeholder={t("objectValueEditor.keyPlaceholder")}
              className="flex-1 h-8 text-xs"
            />
            <Select
              value={row.type}
              onValueChange={(value) =>
                handleTypeChange(row.id, value as ValueType)
              }
            >
              <SelectTrigger size="sm" className="w-[96px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="string">string</SelectItem>
                <SelectItem value="number">number</SelectItem>
                <SelectItem value="boolean">boolean</SelectItem>
                <SelectItem value="object">object</SelectItem>
              </SelectContent>
            </Select>

            {row.type !== "object" && (
              <div className="flex-1">
                {row.type === "boolean" ? (
                  <Select
                    value={row.booleanValue ? "true" : "false"}
                    onValueChange={(value) =>
                      updateRow(row.id, { booleanValue: value === "true" })
                    }
                  >
                    <SelectTrigger size="sm" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">true</SelectItem>
                      <SelectItem value="false">false</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={row.primitive}
                    onChange={(e) =>
                      updateRow(row.id, { primitive: e.target.value })
                    }
                    type={row.type === "number" ? "number" : "text"}
                    placeholder={t("objectValueEditor.valuePlaceholder")}
                    className="h-8 text-xs"
                  />
                )}
              </div>
            )}

            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              onClick={() => removeRow(row.id)}
              aria-label={t("common.delete")}
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>

          {row.type === "object" && (
            <ObjectConstructor
              rows={row.children}
              onChange={(children) => updateRow(row.id, { children })}
              depth={depth + 1}
            />
          )}
        </div>
      ))}

      <Button
        type="button"
        size="sm"
        variant="ghost"
        onClick={addRow}
        className="self-start text-xs"
      >
        <Plus className="size-3.5 mr-1" />
        {t("objectValueEditor.addKey")}
      </Button>
    </div>
  );
};
