import { Switch } from "@/shared/ui/switch";
import { Label } from "@/shared/ui/label";
import type { NodeProperty } from "../../../../../../model/types";

interface BooleanFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

export const BooleanField = ({ property, value, onChange }: BooleanFieldProps) => (
  <div className="space-y-1.5">
    <div className="flex items-center justify-between gap-4">
      <Label className="text-xs">{property.displayName}</Label>
      <Switch
        checked={typeof value === "boolean" ? value : false}
        onCheckedChange={(checked) => onChange(checked)}
        showIcons={false}
      />
    </div>
    {property.description && (
      <p className="text-[10px] text-muted-foreground">{property.description}</p>
    )}
  </div>
);
