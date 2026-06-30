import { useTranslation } from "react-i18next";
import { Textarea } from "@/shared/ui/textarea";
import { Label } from "@/shared/ui/label";
import type { NodeProperty } from "../../../../../../model/types";

interface JsonFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

const toDisplayString = (v: unknown): string => {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return "";
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return "";
  }
};

export const JsonField = ({ property, value, onChange }: JsonFieldProps) => {
  const { t } = useTranslation();

  const handleChange = (raw: string) => {
    // Store as string; consumers parse as needed.
    onChange(raw);
  };

  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{property.displayName}</Label>
      <Textarea
        className="text-xs font-mono resize-none"
        value={toDisplayString(value)}
        placeholder={property.placeholder ?? t("nodeForms.generic.jsonPlaceholder")}
        onChange={(e) => handleChange(e.target.value)}
      />
      {property.description && (
        <p className="text-[10px] text-muted-foreground">{property.description}</p>
      )}
    </div>
  );
};
