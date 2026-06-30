import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Button } from "@/shared/ui/button";
import { PlusIcon, TrashIcon } from "lucide-react";
import type { NodeProperty } from "../../../../../../model/types";

interface KeyValueFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

const toRecord = (v: unknown): Record<string, string> => {
  if (v !== null && typeof v === "object" && !Array.isArray(v)) {
    return v as Record<string, string>;
  }
  return {};
};

export const KeyValueField = ({ property, value, onChange }: KeyValueFieldProps) => {
  const { t } = useTranslation();

  // Monotonic counter for collision-free generated keys (survives mid-list deletes).
  const counterRef = useRef(0);
  const nextKey = () => {
    counterRef.current += 1;
    return `key_${counterRef.current}`;
  };

  const record = toRecord(value);
  const entries = Object.entries(record);

  const add = () => {
    onChange({ ...record, [nextKey()]: "" });
  };

  const updateKey = (oldKey: string, newKey: string) => {
    if (oldKey === newKey) return;
    const next = { ...record };
    const val = next[oldKey];
    delete next[oldKey];
    next[newKey] = val ?? "";
    onChange(next);
  };

  const updateValue = (key: string, val: string) => {
    onChange({ ...record, [key]: val });
  };

  const remove = (key: string) => {
    const next = { ...record };
    delete next[key];
    onChange(next);
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label className="text-xs">{property.displayName}</Label>
        <Button type="button" size="icon-sm" variant="ghost" onClick={add}>
          <PlusIcon />
        </Button>
      </div>
      <div className="flex flex-col gap-2">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2 items-center">
            <Input
              className="text-xs flex-1"
              value={k}
              placeholder={t("objectValueEditor.keyPlaceholder")}
              onChange={(e) => updateKey(k, e.target.value)}
            />
            <Input
              className="text-xs flex-1"
              value={v}
              placeholder={t("objectValueEditor.valuePlaceholder")}
              onChange={(e) => updateValue(k, e.target.value)}
            />
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              onClick={() => remove(k)}
            >
              <TrashIcon className="size-3" />
            </Button>
          </div>
        ))}
      </div>
      {property.description && (
        <p className="text-[10px] text-muted-foreground">{property.description}</p>
      )}
    </div>
  );
};
