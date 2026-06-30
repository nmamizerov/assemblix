import { useState } from "react";
import { Button } from "@/shared/ui/button";
import { Label } from "@/shared/ui/label";
import { PlusIcon, TrashIcon } from "lucide-react";
import type { NodeProperty } from "../../../../../../model/types";

interface CollectionFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
  /** renderField passed from the parent switch to avoid circular imports */
  renderField: (
    prop: NodeProperty,
    val: unknown,
    onFieldChange: (value: unknown) => void,
  ) => React.ReactNode;
}

/** Internal row shape: stable id exists only in component state, not in node config. */
interface Row {
  id: string;
  data: Record<string, unknown>;
}

const toArray = (v: unknown): Record<string, unknown>[] => {
  if (Array.isArray(v)) return v as Record<string, unknown>[];
  return [];
};

const buildDefaultItem = (fields: NodeProperty[]): Record<string, unknown> => {
  const item: Record<string, unknown> = {};
  for (const f of fields) {
    item[f.name] = f.default ?? "";
  }
  return item;
};

const makeId = () => crypto.randomUUID();

export const CollectionField = ({
  property,
  value,
  onChange,
  renderField,
}: CollectionFieldProps) => {
  const subFields = property.fields ?? [];

  // Wrap incoming data items with stable ids on first render.
  const [rows, setRows] = useState<Row[]>(() =>
    toArray(value).map((data) => ({ id: makeId(), data })),
  );

  /** Sync rows state and notify parent with plain data array (no ids). */
  const commit = (next: Row[]) => {
    setRows(next);
    onChange(next.map((r) => r.data));
  };

  const addItem = () => {
    commit([
      ...rows,
      { id: makeId(), data: buildDefaultItem(subFields) },
    ]);
  };

  const removeItem = (id: string) => {
    commit(rows.filter((r) => r.id !== id));
  };

  const updateItemField = (id: string, fieldName: string, fieldValue: unknown) => {
    commit(
      rows.map((r) =>
        r.id === id ? { ...r, data: { ...r.data, [fieldName]: fieldValue } } : r,
      ),
    );
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label className="text-xs">{property.displayName}</Label>
        <Button type="button" size="icon-sm" variant="ghost" onClick={addItem}>
          <PlusIcon />
        </Button>
      </div>

      <div className="flex flex-col gap-3">
        {rows.map((row) => (
          <div
            key={row.id}
            className="rounded-md border border-border p-2 space-y-2 relative"
          >
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              className="absolute top-1 right-1"
              onClick={() => removeItem(row.id)}
            >
              <TrashIcon className="size-3" />
            </Button>

            {subFields.map((subProp) =>
              renderField(
                subProp,
                row.data[subProp.name],
                (v) => updateItemField(row.id, subProp.name, v),
              ),
            )}
          </div>
        ))}
      </div>

      {property.description && (
        <p className="text-[10px] text-muted-foreground">{property.description}</p>
      )}
    </div>
  );
};
