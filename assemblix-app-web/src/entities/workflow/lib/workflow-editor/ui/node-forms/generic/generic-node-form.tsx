import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BaseForm } from "../base-form";
import { useNodeDataChange } from "../useNodeDataChange";
import { renderField, isVisible } from "./fields";
import type { NodeDescriptor } from "@/entities/workflow/model/types";
import { snakeToCamel } from "@/shared/lib/utils";

export interface GenericNodeFormProps {
  nodeId: string;
  descriptor: NodeDescriptor;
  config?: Record<string, unknown>;
  projectId?: string;
}

/**
 * Data-driven form rendered from a NodeDescriptor.
 *
 * Key naming: descriptor property.name is snake_case (from backend).
 * Node config stored in ReactFlow data is camelCase (the frontend canonical form).
 * This component translates between them via snakeToCamel on every read/write.
 */
export const GenericNodeForm = ({
  nodeId,
  descriptor,
  config,
  projectId,
}: GenericNodeFormProps) => {
  const { t } = useTranslation();
  const handleDataChange = useNodeDataChange(nodeId);

  // Build initial state: for each property convert snake_case name → camelCase key
  const buildInitial = (): Record<string, unknown> => {
    const initial: Record<string, unknown> = {};
    for (const prop of descriptor.properties) {
      const key = snakeToCamel(prop.name);
      initial[key] = config?.[key] ?? prop.default ?? undefined;
    }
    return initial;
  };

  const [formData, setFormData] = useState<Record<string, unknown>>(buildInitial);

  // Sync ReactFlow node data on every form change
  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  // Snapshot the current camelCase form values into a plain object.
  // This base map only contains camelCase keys — snake_case resolution for
  // showWhen.field (which may arrive snake_case from the backend) is handled
  // per-property in the loop below where we have access to each prop's showWhen.
  const visibilityValues: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(formData)) {
    visibilityValues[k] = v;
  }

  const label = descriptor.displayName ?? t("workflow.editor.nodeEditor");

  return (
    <BaseForm
      nodeType={descriptor.type}
      label={label}
      description={descriptor.description}
      projectId={projectId}
    >
      <div className="space-y-4">
        {descriptor.properties.map((prop) => {
          const camelKey = snakeToCamel(prop.name);

          // isVisible compares prop.showWhen.field against keys in valuesForVisibility.
          // showWhen.field is the raw backend name and may be snake_case, while
          // formData uses camelCase keys. Resolve the backend field name to its
          // camelCase equivalent so the comparison always finds a value.
          const valuesForVisibility: Record<string, unknown> = { ...visibilityValues };
          if (prop.showWhen) {
            const whenKey = prop.showWhen.field;
            valuesForVisibility[whenKey] = formData[snakeToCamel(whenKey)] ?? formData[whenKey];
          }

          if (!isVisible(prop, valuesForVisibility)) return null;

          return renderField(
            prop,
            formData[camelKey],
            (value) => {
              setFormData((prev) => ({ ...prev, [camelKey]: value }));
            },
          );
        })}
      </div>
    </BaseForm>
  );
};
