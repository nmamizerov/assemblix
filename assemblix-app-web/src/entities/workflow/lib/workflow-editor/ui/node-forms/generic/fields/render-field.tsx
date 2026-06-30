import type { ReactNode } from "react";
import type { NodeProperty } from "../../../../../../model/types";

import { StringField } from "./string-field";
import { NumberField } from "./number-field";
import { TextField } from "./text-field";
import { BooleanField } from "./boolean-field";
import { OptionsField } from "./options-field";
import { JsonField } from "./json-field";
import { CodeField } from "./code-field";
import { KeyValueField } from "./key-value-field";
import { CredentialField } from "./credential-field";
import { KnowledgeBaseField } from "./knowledge-base-field";
import { CollectionField } from "./collection-field";

// ---- Visibility helper ----

export const isVisible = (
  p: NodeProperty,
  values: Record<string, unknown>,
): boolean => {
  if (!p.showWhen) return true;
  const current = values[p.showWhen.field];
  return p.showWhen.values.includes(current);
};

// ---- renderField switch ----

export const renderField = (
  property: NodeProperty,
  value: unknown,
  onChange: (value: unknown) => void,
): ReactNode => {
  switch (property.type) {
    case "string":
      return <StringField key={property.name} property={property} value={value} onChange={onChange} />;
    case "number":
      return <NumberField key={property.name} property={property} value={value} onChange={onChange} />;
    case "text":
      return <TextField key={property.name} property={property} value={value} onChange={onChange} />;
    case "boolean":
      return <BooleanField key={property.name} property={property} value={value} onChange={onChange} />;
    case "options":
      return <OptionsField key={property.name} property={property} value={value} onChange={onChange} />;
    case "json":
      return <JsonField key={property.name} property={property} value={value} onChange={onChange} />;
    case "code":
      return <CodeField key={property.name} property={property} value={value} onChange={onChange} />;
    case "key_value":
      return <KeyValueField key={property.name} property={property} value={value} onChange={onChange} />;
    case "credential":
      return <CredentialField key={property.name} property={property} value={value} onChange={onChange} />;
    case "knowledge_base":
      return <KnowledgeBaseField key={property.name} property={property} value={value} onChange={onChange} />;
    case "collection":
      return (
        <CollectionField
          key={property.name}
          property={property}
          value={value}
          onChange={onChange}
          renderField={renderField}
        />
      );
    default:
      return null;
  }
};
