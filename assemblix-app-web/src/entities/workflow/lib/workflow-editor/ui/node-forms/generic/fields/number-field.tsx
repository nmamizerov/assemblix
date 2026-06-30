import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import type { NodeProperty } from "../../../../../../model/types";

interface NumberFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

export const NumberField = ({ property, value, onChange }: NumberFieldProps) => {
  const handleChange = (raw: string) => {
    if (raw === "") {
      onChange(undefined);
      return;
    }
    const num = Number(raw);
    if (!Number.isNaN(num)) onChange(num);
  };

  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{property.displayName}</Label>
      <Input
        type="number"
        className="text-xs"
        value={typeof value === "number" ? value : ""}
        placeholder={property.placeholder ?? ""}
        onChange={(e) => handleChange(e.target.value)}
      />
      {property.description && (
        <p className="text-[10px] text-muted-foreground">{property.description}</p>
      )}
    </div>
  );
};
