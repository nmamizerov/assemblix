import type { StateVariable } from "../../../model/types";

export const generateHandleId = (
  type: "source" | "target",
  nodeId: string,
  index: number
) => {
  return `${type}_${nodeId}_${index}`;
};

/**
 * Рекурсивно парсит JSON схему и преобразует в плоский список переменных с полными путями
 * @param schema - OpenAPI JSON Schema
 * @param prefix - Префикс для пути (по умолчанию "parsed_message")
 * @returns Массив StateVariable с полными путями (например: parsed_message.user.name)
 */
export const flattenSchemaToVariables = (
  schema: Record<string, unknown>,
  prefix = "parsed_message"
): StateVariable[] => {
  const variables: StateVariable[] = [];

  if (!schema || typeof schema !== "object" || !schema.properties) {
    return variables;
  }

  const properties = schema.properties as Record<string, unknown>;

  Object.entries(properties).forEach(([key, value]) => {
    const prop = value as Record<string, unknown>;
    const currentPath = prefix ? `${prefix}.${key}` : key;

    // Определяем тип переменной
    let varType: StateVariable["type"] = "string";
    if (prop.type === "number") {
      varType = "number";
    } else if (prop.type === "boolean") {
      varType = "boolean";
    } else if (prop.type === "object") {
      varType = "object";
    }

    // Если это объект с вложенными свойствами
    if (prop.type === "object" && prop.properties) {
      // Рекурсивно обходим вложенные свойства
      const nestedVars = flattenSchemaToVariables(
        prop as Record<string, unknown>,
        currentPath
      );
      variables.push(...nestedVars);
    }
    // Если это массив
    else if (prop.type === "array" && prop.items) {
      const items = prop.items as Record<string, unknown>;
      const arrayPath = `${currentPath}[0]`;

      // Если элементы массива - объекты, обходим их свойства
      if (items.type === "object" && items.properties) {
        const nestedVars = flattenSchemaToVariables(
          items as Record<string, unknown>,
          arrayPath
        );
        variables.push(...nestedVars);
      } else {
        // Простой массив (строк, чисел и т.д.)
        let itemType: StateVariable["type"] = "string";
        if (items.type === "number") {
          itemType = "number";
        } else if (items.type === "boolean") {
          itemType = "boolean";
        }

        variables.push({
          name: arrayPath,
          type: itemType,
        });
      }
    }
    // Простое свойство (string, number, boolean)
    else {
      variables.push({
        name: currentPath,
        type: varType,
      });
    }
  });

  return variables;
};
