import type { SchemaProperty, OpenAPISchema } from "./types";

/**
 * Конвертирует одно SchemaProperty в узел OpenAPI-схемы.
 * Симметрична parseSchemaNodeToProperty: generate → parse → generate
 * должен быть идемпотентным (см. schema-utils.test.ts).
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

  // Обработка enum
  if (prop.type === "enum" && prop.enumValues && prop.enumValues.length > 0) {
    schemaProp.enum = prop.enumValues.filter((v) => v !== "");
  }

  // Обработка object: properties/additionalProperties пишем всегда, даже для
  // пустого объекта — strict-провайдеры (OpenAI structured outputs) отклоняют
  // {"type": "object"} без properties.
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

  // Обработка array: элементы конвертируются рекурсивно, чтобы объекты,
  // enum'ы и вложенные массивы внутри массива не терялись.
  if (prop.type === "array") {
    schemaProp.items = prop.items
      ? convertPropertyToSchemaNode(prop.items)
      : { type: "string" };
  }

  return schemaProp;
};

/**
 * Конвертирует массив SchemaProperty в OpenAPI схему свойств
 */
export const convertPropertiesToSchema = (
  properties: SchemaProperty[]
): Record<string, unknown> => {
  const result: Record<string, unknown> = {};

  properties.forEach((prop) => {
    if (!prop.name) return; // Пропускаем свойства без имени
    result[prop.name] = convertPropertyToSchemaNode(prop);
  });

  return result;
};

/**
 * Генерирует OpenAPI JSON Schema из массива свойств
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
 * Парсит один узел схемы обратно в SchemaProperty.
 * Рекурсивно восстанавливает вложенные объекты, enum'ы и элементы массивов —
 * в том числе объекты внутри массивов (раньше их поля здесь терялись).
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

  // Восстанавливаем enum значения
  if (property.type === "enum" && Array.isArray(node.enum)) {
    property.enumValues = node.enum as string[];
  }

  // Восстанавливаем вложенные объекты
  if (property.type === "object") {
    property.properties = parseSchemaToProperties({
      type: "object",
      properties: (node.properties as Record<string, unknown>) || {},
      required: (node.required as string[]) || [],
      additionalProperties: false,
    });
  }

  // Восстанавливаем элементы массива (рекурсивно, включая object/enum/array)
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
 * Парсит OpenAPI схему обратно в массив SchemaProperty
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
