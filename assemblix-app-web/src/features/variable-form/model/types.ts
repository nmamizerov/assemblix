export type VariableType = "string" | "number" | "boolean" | "object";

export interface VariableFormData {
  name: string;
  type: VariableType;
  defaultValue?: string | number | boolean | Record<string, unknown> | null;
  isProjectVariable?: boolean;
}
