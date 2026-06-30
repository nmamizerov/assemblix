import type { SchemaProperty, OpenAPISchema } from "./types";

/**
 * Конвертирует массив SchemaProperty в OpenAPI схему свойств
 */
export const convertPropertiesToSchema = (
  properties: SchemaProperty[]
): Record<string, unknown> => {
  const result: Record<string, unknown> = {};

  properties.forEach((prop) => {
    if (!prop.name) return; // Пропускаем свойства без имени

    const schemaProp: Record<string, unknown> = {
      type: prop.type === "enum" ? "string" : prop.type,
    };

    if (prop.description) {
      schemaProp.description = prop.description;
    }

    // Обработка enum
    if (
      prop.type === "enum" &&
      prop.enumValues &&
      prop.enumValues.length > 0
    ) {
      schemaProp.enum = prop.enumValues.filter((v) => v !== "");
    }

    // Обработка object
    if (
      prop.type === "object" &&
      prop.properties &&
      prop.properties.length > 0
    ) {
      schemaProp.properties = convertPropertiesToSchema(prop.properties);
      const requiredProps = prop.properties
        .filter((p) => p.required && p.name)
        .map((p) => p.name);
      if (requiredProps.length > 0) {
        schemaProp.required = requiredProps;
      }
      schemaProp.additionalProperties = false;
    }

    // Обработка array
    if (prop.type === "array" && prop.items) {
      const itemSchema = convertPropertiesToSchema([prop.items]);
      schemaProp.items = itemSchema[prop.items.name] || { type: "string" };
    }

    result[prop.name] = schemaProp;
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
 * Парсит OpenAPI схему обратно в массив SchemaProperty
 */
export const parseSchemaToProperties = (
  schema?: OpenAPISchema
): SchemaProperty[] => {
  if (!schema || !schema.properties) return [];

  const properties: SchemaProperty[] = [];
  const required = schema.required || [];

  Object.entries(schema.properties).forEach(([name, value]) => {
    const prop = value as Record<string, unknown>;
    const property: SchemaProperty = {
      id: crypto.randomUUID(),
      name,
      type: (prop.enum ? "enum" : prop.type) as SchemaProperty["type"],
      description: (prop.description as string) || "",
      required: required.includes(name),
    };

    // Восстанавливаем enum значения
    if (property.type === "enum" && Array.isArray(prop.enum)) {
      property.enumValues = prop.enum as string[];
    }

    // Восстанавливаем вложенные объекты
    if (property.type === "object" && prop.properties) {
      property.properties = parseSchemaToProperties({
        type: "object",
        properties: prop.properties as Record<string, unknown>,
        required: (prop.required as string[]) || [],
        additionalProperties: false,
      });
    }

    // Восстанавливаем массивы
    if (property.type === "array" && prop.items) {
      const items = prop.items as Record<string, unknown>;
      property.items = {
        id: crypto.randomUUID(),
        name: "item",
        type: items.type as SchemaProperty["type"],
        description: (items.description as string) || "",
      };
    }

    properties.push(property);
  });

  return properties;
};
