import type {
  JsonObject,
  JsonValue,
  PropertyRow,
  ValueType,
} from "./types";

const createId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const inferType = (value: JsonValue): ValueType => {
  if (typeof value === "string") return "string";
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return "object";
  }
  return "string";
};

export const objectToRows = (obj: JsonObject | null | undefined): PropertyRow[] => {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];

  return Object.entries(obj).map(([key, value]) => {
    const type = inferType(value);
    const row: PropertyRow = {
      id: createId(),
      key,
      type,
      primitive: "",
      booleanValue: false,
      children: [],
    };

    if (type === "boolean") {
      row.booleanValue = Boolean(value);
    } else if (type === "object") {
      row.children = objectToRows(value as JsonObject);
    } else if (type === "number") {
      row.primitive = value === null ? "" : String(value);
    } else if (type === "string") {
      row.primitive = typeof value === "string" ? value : "";
    }

    return row;
  });
};

export const rowsToObject = (rows: PropertyRow[]): JsonObject => {
  const result: JsonObject = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) continue;

    switch (row.type) {
      case "string":
        result[key] = row.primitive;
        break;
      case "number": {
        if (row.primitive === "") {
          result[key] = null;
          break;
        }
        const parsed = Number(row.primitive);
        result[key] = Number.isNaN(parsed) ? row.primitive : parsed;
        break;
      }
      case "boolean":
        result[key] = row.booleanValue;
        break;
      case "object":
        result[key] = rowsToObject(row.children);
        break;
    }
  }
  return result;
};

export const createEmptyRow = (): PropertyRow => ({
  id: createId(),
  key: "",
  type: "string",
  primitive: "",
  booleanValue: false,
  children: [],
});
