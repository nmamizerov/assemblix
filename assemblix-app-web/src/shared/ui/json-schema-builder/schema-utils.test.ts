import { describe, it, expect } from "vitest";
import type { SchemaProperty, OpenAPISchema } from "./types";
import { generateSchema, parseSchemaToProperties } from "./schema-utils";

/**
 * Регрессионные тесты на потерю данных в round-trip'е generate → parse →
 * generate: parseSchemaToProperties вызывается при каждом открытии модалки
 * схемы и при переключении Simple/Advanced, поэтому цикл обязан быть
 * идемпотентным. Раньше объекты (и enum'ы, и вложенные массивы) внутри
 * массива теряли содержимое, и на бэкенд уходил невалидный для strict-режима
 * {"type": "object"} без properties.
 */

const prop = (overrides: Partial<SchemaProperty>): SchemaProperty => ({
  id: crypto.randomUUID(),
  name: "",
  type: "string",
  description: "",
  ...overrides,
});

const roundTrip = (schema: OpenAPISchema): OpenAPISchema =>
  generateSchema(parseSchemaToProperties(schema), schema.title);

describe("generateSchema", () => {
  it("emits properties + additionalProperties even for an empty object", () => {
    const schema = generateSchema([prop({ name: "blob", type: "object" })]);

    expect(schema.properties.blob).toEqual({
      type: "object",
      properties: {},
      additionalProperties: false,
    });
  });

  it("recursively converts an object inside an array", () => {
    const schema = generateSchema([
      prop({
        name: "results",
        type: "array",
        items: prop({
          name: "item",
          type: "object",
          properties: [
            prop({ name: "title", type: "string", required: true }),
          ],
        }),
      }),
    ]);

    expect(schema.properties.results).toEqual({
      type: "array",
      items: {
        type: "object",
        properties: { title: { type: "string" } },
        required: ["title"],
        additionalProperties: false,
      },
    });
  });
});

describe("generate → parse → generate round-trip", () => {
  it("is idempotent for an object inside an array (the reported bug)", () => {
    const schema = generateSchema([
      prop({
        name: "results",
        type: "array",
        items: prop({
          name: "item",
          type: "object",
          properties: [
            prop({ name: "title", type: "string", required: true }),
            prop({ name: "score", type: "number" }),
          ],
        }),
      }),
    ]);

    expect(roundTrip(schema)).toEqual(schema);
    expect(roundTrip(roundTrip(schema))).toEqual(schema);
  });

  it("preserves an enum inside an array", () => {
    const schema = generateSchema([
      prop({
        name: "tags",
        type: "array",
        items: prop({
          name: "item",
          type: "enum",
          enumValues: ["red", "green"],
        }),
      }),
    ]);

    expect(roundTrip(schema)).toEqual(schema);
  });

  it("preserves a nested array of arrays", () => {
    const schema = generateSchema([
      prop({
        name: "matrix",
        type: "array",
        items: prop({
          name: "item",
          type: "array",
          items: prop({ name: "item", type: "number" }),
        }),
      }),
    ]);

    expect(roundTrip(schema)).toEqual(schema);
  });

  it("preserves top-level required flags and descriptions", () => {
    const schema = generateSchema(
      [
        prop({
          name: "answer",
          type: "string",
          description: "final answer",
          required: true,
        }),
        prop({ name: "confidence", type: "number" }),
      ],
      "mySchema"
    );

    expect(roundTrip(schema)).toEqual(schema);
    expect(schema.required).toEqual(["answer"]);
    expect(schema.title).toBe("mySchema");
  });
});

describe("parseSchemaToProperties", () => {
  it("restores nested properties of an object inside an array", () => {
    const parsed = parseSchemaToProperties({
      type: "object",
      additionalProperties: false,
      properties: {
        results: {
          type: "array",
          items: {
            type: "object",
            properties: { title: { type: "string" } },
            required: ["title"],
            additionalProperties: false,
          },
        },
      },
    });

    const items = parsed[0].items;
    expect(items?.type).toBe("object");
    expect(items?.properties).toHaveLength(1);
    expect(items?.properties?.[0]).toMatchObject({
      name: "title",
      type: "string",
      required: true,
    });
  });
});
