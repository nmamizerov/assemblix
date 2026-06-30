/**
 * Типы свойств JSON Schema
 */
export type SchemaPropertyType =
  | "string"
  | "number"
  | "boolean"
  | "enum"
  | "object"
  | "array";

/**
 * Интерфейс свойства JSON Schema
 */
export interface SchemaProperty {
  id: string;
  name: string;
  type: SchemaPropertyType;
  description: string;
  required?: boolean;
  enumValues?: string[]; // для enum
  properties?: SchemaProperty[]; // для object
  items?: SchemaProperty; // для array
}

/**
 * OpenAPI JSON Schema
 */
export interface OpenAPISchema {
  type: string;
  properties: Record<string, unknown>;
  required?: string[];
  additionalProperties: boolean;
  title?: string;
}

/**
 * Лейблы для типов
 */
export const TYPE_LABELS: Record<SchemaPropertyType, string> = {
  string: "STR",
  number: "NUM",
  boolean: "BOOL",
  enum: "ENUM",
  object: "OBJ",
  array: "ARR",
};

/**
 * Иконки для типов
 */
export const TYPE_ICONS: Record<SchemaPropertyType, string> = {
  string: '"',
  number: "#",
  boolean: "◉",
  enum: "⠿",
  object: "{}",
  array: "[]",
};
