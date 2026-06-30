import { Label } from "@/shared/ui/label";
import { CredentialSelect } from "@/entities/credential";
import type { NodeProperty } from "../../../../../../model/types";

interface CredentialFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

/**
 * Credential picker field.
 * Reuses CredentialSelect from entities/credential.
 * No credentialType filter is applied here because the generic descriptor
 * does not carry CredentialType; A11/GenericNodeForm can pass it if needed.
 */
export const CredentialField = ({ property, value, onChange }: CredentialFieldProps) => (
  <div className="space-y-1.5">
    <Label className="text-xs">{property.displayName}</Label>
    <CredentialSelect
      selectedCredentialId={typeof value === "string" ? value : ""}
      onSelect={(id) => onChange(id)}
      placeholder={property.placeholder}
    />
    {property.description && (
      <p className="text-[10px] text-muted-foreground">{property.description}</p>
    )}
  </div>
);
