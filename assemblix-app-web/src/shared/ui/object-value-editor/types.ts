export type JsonPrimitive = string | number | boolean | null;
export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export type ValueType = "string" | "number" | "boolean" | "object";

export interface PropertyRow {
  id: string;
  key: string;
  type: ValueType;
  primitive: string;
  booleanValue: boolean;
  children: PropertyRow[];
}
