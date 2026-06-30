import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import type { NodeProperty } from "../../../../../../model/types";

interface StringFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

export const StringField = ({ property, value, onChange }: StringFieldProps) => (
  <div className="space-y-1.5">
    <Label className="text-xs">{property.displayName}</Label>
    <Input
      className="text-xs"
      value={typeof value === "string" ? value : ""}
      placeholder={property.placeholder ?? ""}
      onChange={(e) => onChange(e.target.value)}
    />
    {property.description && (
      <p className="text-[10px] text-muted-foreground">{property.description}</p>
    )}
  </div>
);
