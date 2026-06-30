import { Textarea } from "@/shared/ui/textarea";
import { Label } from "@/shared/ui/label";
import type { NodeProperty } from "../../../../../../model/types";

interface TextFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

export const TextField = ({ property, value, onChange }: TextFieldProps) => (
  <div className="space-y-1.5">
    <Label className="text-xs">{property.displayName}</Label>
    <Textarea
      className="text-xs resize-none"
      value={typeof value === "string" ? value : ""}
      placeholder={property.placeholder ?? ""}
      onChange={(e) => onChange(e.target.value)}
    />
    {property.description && (
      <p className="text-[10px] text-muted-foreground">{property.description}</p>
    )}
  </div>
);
