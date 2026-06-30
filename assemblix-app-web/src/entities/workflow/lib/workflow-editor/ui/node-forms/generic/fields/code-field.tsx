import { CELTextarea } from "@/shared/ui/cel-input";
import { Label } from "@/shared/ui/label";
import type { NodeProperty } from "../../../../../../model/types";

interface CodeFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

/**
 * Code / CEL expression field.
 * Reuses the same CELTextarea that condition-node-form uses,
 * but without the workflow variable suggestions popover wiring
 * (that requires workflow context not available at this layer).
 * A11/GenericNodeForm can layer that on top if needed.
 */
export const CodeField = ({ property, value, onChange }: CodeFieldProps) => (
  <div className="space-y-1.5">
    <Label className="text-xs">{property.displayName}</Label>
    <CELTextarea
      className="text-xs placeholder:text-xs"
      value={typeof value === "string" ? value : ""}
      placeholder={property.placeholder ?? ""}
      onChange={(v) => onChange(v)}
    />
    {property.description && (
      <p className="text-[10px] text-muted-foreground">{property.description}</p>
    )}
  </div>
);
