import type { SchemaProperty, OpenAPISchema } from "./types";

/**
 * Converts a single SchemaProperty into an OpenAPI schema node.
 * Symmetric with parseSchemaNodeToProperty: the generate → parse → generate
 * round-trip must be idempotent (see schema-utils.test.ts).
 */
const convertPropertyToSchemaNode = (
  prop: SchemaProperty
): Record<string, unknown> => {
  const schemaProp: Record<string, unknown> = {
    type: prop.type === "enum" ? "string" : prop.type,
  };

  if (prop.description) {
    schemaProp.description = prop.description;
  }

  // Enum handling
  if (prop.type === "enum" && prop.enumValues && prop.enumValues.length > 0) {
    schemaProp.enum = prop.enumValues.filter((v) => v !== "");
  }

  // Object handling: always emit properties/additionalProperties, even for an
  // empty object — strict providers (OpenAI structured outputs) reject
  // {"type": "object"} without properties.
  if (prop.type === "object") {
    schemaProp.properties = convertPropertiesToSchema(prop.properties || []);
    const requiredProps = (prop.properties || [])
      .filter((p) => p.required && p.name)
      .map((p) => p.name);
    if (requiredProps.length > 0) {
      schemaProp.required = requiredProps;
    }
    schemaProp.additionalProperties = false;
  }

  // Array handling: items are converted recursively so that objects, enums
  // and nested arrays inside an array are not lost.
  if (prop.type === "array") {
    schemaProp.items = prop.items
      ? convertPropertyToSchemaNode(prop.items)
      : { type: "string" };
  }

  return schemaProp;
};

/**
 * Converts an array of SchemaProperty into an OpenAPI properties map
 */
export const convertPropertiesToSchema = (
  properties: SchemaProperty[]
): Record<string, unknown> => {
  const result: Record<string, unknown> = {};

  properties.forEach((prop) => {
    if (!prop.name) return; // Skip unnamed properties
    result[prop.name] = convertPropertyToSchemaNode(prop);
  });

  return result;
};

/**
 * Generates an OpenAPI JSON Schema from an array of properties
 */
export const generateSchema = (
  properties: SchemaProperty[],
  title: string = "responseSchema"
): OpenAPISchema => {
  const requiredProps = properties
    .filter((p) => p.required && p.name)
    .map((p) => p.name);

  const schema: OpenAPISchema = {
    type: "object",
    properties: convertPropertiesToSchema(properties),
    additionalProperties: false,
    title,
  };

  if (requiredProps.length > 0) {
    schema.required = requiredProps;
  }

  return schema;
};

/**
 * Parses a single schema node back into a SchemaProperty.
 * Recursively restores nested objects, enums and array items — including
 * objects inside arrays (their fields used to be lost here).
 */
const parseSchemaNodeToProperty = (
  name: string,
  node: Record<string, unknown>,
  required: boolean
): SchemaProperty => {
  const property: SchemaProperty = {
    id: crypto.randomUUID(),
    name,
    type: (node.enum ? "enum" : node.type) as SchemaProperty["type"],
    description: (node.description as string) || "",
    required,
  };

  // Restore enum values
  if (property.type === "enum" && Array.isArray(node.enum)) {
    property.enumValues = node.enum as string[];
  }

  // Restore nested objects
  if (property.type === "object") {
    property.properties = parseSchemaToProperties({
      type: "object",
      properties: (node.properties as Record<string, unknown>) || {},
      required: (node.required as string[]) || [],
      additionalProperties: false,
    });
  }

  // Restore array items (recursively, including object/enum/array)
  if (property.type === "array" && node.items) {
    property.items = parseSchemaNodeToProperty(
      "item",
      node.items as Record<string, unknown>,
      false
    );
  }

  return property;
};

/**
 * Parses an OpenAPI schema back into an array of SchemaProperty
 */
export const parseSchemaToProperties = (
  schema?: OpenAPISchema
): SchemaProperty[] => {
  if (!schema || !schema.properties) return [];

  const required = schema.required || [];

  return Object.entries(schema.properties).map(([name, value]) =>
    parseSchemaNodeToProperty(
      name,
      value as Record<string, unknown>,
      required.includes(name)
    )
  );
};
