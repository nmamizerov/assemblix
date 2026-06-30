import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Label } from "@/shared/ui/label";
import type { NodeProperty } from "../../../../../../model/types";

interface OptionsFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

export const OptionsField = ({ property, value, onChange }: OptionsFieldProps) => {
  const options = property.options ?? [];

  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{property.displayName}</Label>
      <Select
        value={typeof value === "string" ? value : ""}
        onValueChange={(v) => onChange(v)}
      >
        <SelectTrigger className="text-xs">
          <SelectValue placeholder={property.placeholder ?? property.displayName} />
        </SelectTrigger>
        <SelectContent>
          {options.map((opt) => (
            <SelectItem key={opt.value} value={opt.value} className="text-xs">
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {property.description && (
        <p className="text-[10px] text-muted-foreground">{property.description}</p>
      )}
    </div>
  );
};
