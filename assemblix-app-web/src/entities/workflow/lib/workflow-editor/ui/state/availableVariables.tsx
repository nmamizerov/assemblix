import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import type { RootState } from "@/app/store/store";
import { selectVariablesByWorkflowId } from "@/entities/workflow/model/variables.slice";
import type {
  StateVariable,
  Workflow,
  AgentNodeConfig,
} from "@/entities/workflow/model/types";
import { NodeType } from "@/entities/workflow/model/types";
import { Variable } from "@/entities/workflow/ui/variable";
import { useMemo, useEffect, useRef } from "react";
import { cn } from "@/shared/lib/utils";
import { flattenSchemaToVariables } from "../../helpers/utils";
import { useNodes, useEdges } from "@xyflow/react";
import type {
  Node as ReactFlowNode,
  Edge as ReactFlowEdge,
} from "@xyflow/react";
import { selectCurrentProjectId } from "@/entities/organization";
import { useGetProjectQuery } from "@/entities/project";
import type { CELVariableType } from "@/shared/ui/cel-input";

type FlatItem = {
  type: "variable" | "operator";
  prefix?: string;
  variable?: StateVariable;
  operator?: string;
};

interface AvailableVariablesProps {
  term?: string;
  type?: CELVariableType;
  onSelect: (term: string) => void;
  workflow: Workflow;
  onInsertText?: (text: string) => void;
  currentNodeId?: string;
  selectedIndex?: number;
  onItemsChange?: (items: FlatItem[]) => void;
}

// Константа для input переменной
const INPUT_VARIABLE: StateVariable = {
  name: "input_as_text",
  type: "string",
};

const METADATA_VARIABLES: StateVariable[] = [
  { name: "client_id", type: "string" },
  { name: "session_id", type: "string" },
  { name: "execution_id", type: "string" },
];

// Вспомогательные функции для работы с предыдущей нодой

/**
 * Находит ноду, которая является source для текущей ноды (предыдущая нода в потоке)
 * Использует актуальные ноды и edges из React Flow
 */
const getPreviousNode = (
  currentNodeId: string,
  reactFlowNodes: ReactFlowNode[],
  reactFlowEdges: ReactFlowEdge[]
): ReactFlowNode | null => {
  const edge = reactFlowEdges.find((e) => e.target === currentNodeId);
  if (!edge) return null;
  return reactFlowNodes.find((n) => n.id === edge.source) || null;
};

/**
 * Извлекает input переменные из предыдущей ноды (React Flow node)
 * Всегда возвращает input.message + дополнительно parsed_message.* если есть JSON схема
 */
const getInputVariables = (
  previousNode: ReactFlowNode | null
): StateVariable[] => {
  // Базовая переменная message всегда доступна
  const variables: StateVariable[] = [{ name: "message", type: "string" }];

  if (!previousNode) return variables;

  // Если агентская нода с JSON схемой, добавляем parsed_message.*
  if (previousNode.type === NodeType.AGENT) {
    const config = previousNode.data as AgentNodeConfig;
    if (config.responseFormat === "json_object" && config.responseSchema) {
      const parsedVars = flattenSchemaToVariables(
        config.responseSchema as Record<string, unknown>
      );
      variables.push(...parsedVars);
    }
  }

  // Если HTTP Request нода, добавляем output переменные
  if (previousNode.type === NodeType.HTTP_REQUEST) {
    return [
      { name: "status_code", type: "number" },
      { name: "body", type: "object" },
      { name: "headers", type: "object" },
      { name: "ok", type: "boolean" },
    ];
  }

  return variables;
};

export const AvailableVariables = ({
  term = "",
  type,
  onSelect,
  workflow,
  onInsertText,
  currentNodeId,
  selectedIndex = 0,
  onItemsChange,
}: AvailableVariablesProps) => {
  const { t } = useTranslation();

  // Получаем актуальные ноды и edges из React Flow
  const reactFlowNodes = useNodes();
  const reactFlowEdges = useEdges();

  // Получаем текущий проект для доступа к project state schema
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: currentProject } = useGetProjectQuery(currentProjectId!, {
    skip: !currentProjectId,
  });

  // Преобразуем project state schema в StateVariable[]
  const projectVariables = useMemo<StateVariable[]>(() => {
    if (!currentProject?.stateSchema) return [];
    return currentProject.stateSchema.map((v) => ({
      name: v.name,
      type: v.type,
      defaultValue: v.defaultValue as
        | string
        | number
        | boolean
        | null
        | undefined,
    }));
  }, [currentProject]);

  // Константы для операторов (используем переводы)
  const COMPARISON_OPERATORS = useMemo(
    () => [
      {
        name: "==",
        description: t("availableVariables.operators.comparison.equal"),
      },
      {
        name: "!=",
        description: t("availableVariables.operators.comparison.notEqual"),
      },
      {
        name: "<",
        description: t("availableVariables.operators.comparison.less"),
      },
      {
        name: ">",
        description: t("availableVariables.operators.comparison.greater"),
      },
      {
        name: "<=",
        description: t("availableVariables.operators.comparison.lessOrEqual"),
      },
      {
        name: ">=",
        description: t(
          "availableVariables.operators.comparison.greaterOrEqual"
        ),
      },
    ],
    [t]
  );

  const LOGICAL_OPERATORS = useMemo(
    () => [
      {
        name: "?",
        description: t("availableVariables.operators.logical.ternary"),
      },
      { name: "||", description: t("availableVariables.operators.logical.or") },
      {
        name: "&&",
        description: t("availableVariables.operators.logical.and"),
      },
    ],
    [t]
  );

  // Получаем переменные состояния из Redux
  const stateVariables = useSelector((state: RootState) =>
    selectVariablesByWorkflowId(state, workflow.id)
  );

  // Refs для элементов списка
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Фильтруем переменные и операторы в зависимости от типа и терма
  const filteredVariables = useMemo(() => {
    let variables: Array<{ variable: StateVariable; prefix: string }> = [];

    // Определяем, какие переменные показывать
    if (type === "workflow") {
      // Для workflow показываем только input_as_text
      variables.push({ variable: INPUT_VARIABLE, prefix: "workflow" });
    } else if (type === "input") {
      // Для input показываем output предыдущей ноды
      if (currentNodeId && reactFlowNodes.length > 0) {
        const previousNode = getPreviousNode(
          currentNodeId,
          reactFlowNodes,
          reactFlowEdges
        );
        const inputVars = getInputVariables(previousNode);
        inputVars.forEach((v) => {
          variables.push({ variable: v, prefix: "input" });
        });
      }
    } else if (type === "state") {
      // Для state показываем переменные состояния
      stateVariables.forEach((v) => {
        variables.push({ variable: v, prefix: "state" });
      });
    } else if (type === "project") {
      // Для project показываем project переменные
      projectVariables.forEach((v) => {
        variables.push({ variable: v, prefix: "project" });
      });
    } else if (type === "metadata") {
      // Для metadata показываем metadata переменные
      METADATA_VARIABLES.forEach((v) => {
        variables.push({ variable: v, prefix: "metadata" });
      });
    } else if (!type) {
      // Если тип не указан (при частичном вводе или фокусе), показываем ВСЕ переменные
      // 1. workflow.input_as_text
      variables.push({ variable: INPUT_VARIABLE, prefix: "workflow" });

      // 2. input.* (output предыдущей ноды)
      if (currentNodeId && reactFlowNodes.length > 0) {
        const previousNode = getPreviousNode(
          currentNodeId,
          reactFlowNodes,
          reactFlowEdges
        );
        const inputVars = getInputVariables(previousNode);
        inputVars.forEach((v) => {
          variables.push({ variable: v, prefix: "input" });
        });
      }

      // 3. state.*
      stateVariables.forEach((v) => {
        variables.push({ variable: v, prefix: "state" });
      });

      // 4. project.*
      projectVariables.forEach((v) => {
        variables.push({ variable: v, prefix: "project" });
      });

      // 5. metadata.*
      METADATA_VARIABLES.forEach((v) => {
        variables.push({ variable: v, prefix: "metadata" });
      });
    }

    // Фильтруем по терму (поиск по имени переменной или префиксу)
    if (term) {
      variables = variables.filter((v) => {
        const varName = v.variable.name.toLowerCase();
        const prefix = v.prefix.toLowerCase();
        const searchTerm = term.toLowerCase();

        // Проверяем совпадение с именем переменной или префиксом
        return varName.includes(searchTerm) || prefix.includes(searchTerm);
      });
    }

    return variables;
  }, [
    type,
    term,
    stateVariables,
    projectVariables,
    currentNodeId,
    reactFlowNodes,
    reactFlowEdges,
  ]);

  const filteredOperators = useMemo(() => {
    if (type !== "other") return { comparison: [], logical: [] };

    const filterFn = (op: { name: string; description: string }) =>
      op.name.includes(term) ||
      op.description.toLowerCase().includes(term.toLowerCase());

    // Фильтруем по терму если есть
    if (term) {
      return {
        comparison: COMPARISON_OPERATORS.filter(filterFn),
        logical: LOGICAL_OPERATORS.filter(filterFn),
      };
    }

    return {
      comparison: COMPARISON_OPERATORS,
      logical: LOGICAL_OPERATORS,
    };
  }, [type, term, COMPARISON_OPERATORS, LOGICAL_OPERATORS]);

  // Группируем переменные по префиксу
  const groupedVariables = useMemo(() => {
    const groups: Record<string, Array<StateVariable>> = {};

    filteredVariables.forEach(({ variable, prefix }) => {
      if (!groups[prefix]) {
        groups[prefix] = [];
      }
      groups[prefix].push(variable);
    });

    return groups;
  }, [filteredVariables]);

  // Создаем плоский список всех элементов для навигации
  const flatItems = useMemo(() => {
    const items: FlatItem[] = [];

    if (type === "other") {
      // Добавляем операторы
      filteredOperators.comparison.forEach((op) => {
        items.push({ type: "operator", operator: op.name });
      });
      filteredOperators.logical.forEach((op) => {
        items.push({ type: "operator", operator: op.name });
      });
    } else {
      // Добавляем переменные в порядке отображения
      const prefixOrder = ["input", "state", "project", "workflow", "metadata"];
      const sortedPrefixes = Object.keys(groupedVariables).sort(
        (a, b) => prefixOrder.indexOf(a) - prefixOrder.indexOf(b)
      );

      sortedPrefixes.forEach((prefix) => {
        groupedVariables[prefix].forEach((variable) => {
          items.push({ type: "variable", prefix, variable });
        });
      });
    }

    return items;
  }, [type, filteredOperators, groupedVariables]);

  // Уведомляем родителя об изменении списка элементов
  useEffect(() => {
    if (onItemsChange) {
      onItemsChange(flatItems);
    }
  }, [flatItems, onItemsChange]);

  // Прокручиваем к выбранному элементу
  useEffect(() => {
    if (selectedIndex >= 0 && selectedIndex < itemRefs.current.length) {
      itemRefs.current[selectedIndex]?.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [selectedIndex]);

  const handleSelect = (variable: StateVariable, prefix: string) => {
    const fullName = `${prefix}.${variable.name}`;

    // Вставляем переменную через коллбек
    if (onInsertText) {
      onInsertText(fullName);
    }

    // Уведомляем родителя
    onSelect(fullName);
  };

  const handleOperatorSelect = (operator: string) => {
    // Вставляем оператор с пробелами
    const operatorWithSpaces = ` ${operator} `;

    if (onInsertText) {
      onInsertText(operatorWithSpaces);
    }

    // Уведомляем родителя
    onSelect(operatorWithSpaces);
  };

  // Проверяем, есть ли что показывать
  if (type === "other") {
    const hasComparison = filteredOperators.comparison.length > 0;
    const hasLogical = filteredOperators.logical.length > 0;

    if (!hasComparison && !hasLogical) {
      return (
        <div className="p-4 text-center">
          <p className="text-xs text-muted-foreground">
            {term
              ? t("availableVariables.operators.notFound")
              : t("availableVariables.operators.noAvailable")}
          </p>
        </div>
      );
    }

    let currentIndex = 0;

    return (
      <div className="py-2 max-h-[500px] overflow-y-auto">
        {hasComparison && (
          <div className="mb-3">
            <div className="px-3 pb-2">
              <h4 className="text-xs font-semibold text-muted-foreground">
                {t("availableVariables.operators.comparisonTitle")}
              </h4>
            </div>
            <div>
              {filteredOperators.comparison.map((operator) => {
                const itemIndex = currentIndex++;
                const isSelected = itemIndex === selectedIndex;
                return (
                  <button
                    key={operator.name}
                    ref={(el) => {
                      itemRefs.current[itemIndex] = el;
                    }}
                    onClick={() => handleOperatorSelect(operator.name)}
                    className={cn(
                      "w-full px-3 py-2 text-left hover:bg-accent transition-colors flex items-center gap-2",
                      isSelected && "bg-accent"
                    )}
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono font-semibold">
                          {operator.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {operator.description}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {hasLogical && (
          <div>
            <div className="px-3 pb-2">
              <h4 className="text-xs font-semibold text-muted-foreground">
                {t("availableVariables.operators.logicalTitle")}
              </h4>
            </div>
            <div>
              {filteredOperators.logical.map((operator) => {
                const itemIndex = currentIndex++;
                const isSelected = itemIndex === selectedIndex;
                return (
                  <button
                    key={operator.name}
                    ref={(el) => {
                      itemRefs.current[itemIndex] = el;
                    }}
                    onClick={() => handleOperatorSelect(operator.name)}
                    className={cn(
                      "w-full px-3 py-2 text-left hover:bg-accent transition-colors flex items-center gap-2",
                      isSelected && "bg-accent"
                    )}
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono font-semibold">
                          {operator.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {operator.description}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (filteredVariables.length === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-xs text-muted-foreground">
          {term
            ? t("availableVariables.variablesNotFound")
            : t("availableVariables.noAvailableVariables")}
        </p>
      </div>
    );
  }

  // Порядок отображения групп
  const prefixOrder = ["input", "state", "project", "workflow", "metadata"];
  const sortedPrefixes = Object.keys(groupedVariables).sort(
    (a, b) => prefixOrder.indexOf(a) - prefixOrder.indexOf(b)
  );

  // Названия групп с заглавной буквы
  const prefixLabels: Record<string, string> = {
    input: t("availableVariables.groups.input"),
    state: t("availableVariables.groups.state"),
    project: t("availableVariables.groups.project"),
    workflow: t("availableVariables.groups.workflow"),
    metadata: t("availableVariables.groups.metadata"),
  };

  let currentIndex = 0;

  return (
    <div className="py-2 max-h-[500px] overflow-y-auto">
      {sortedPrefixes.map((prefix, groupIndex) => (
        <div key={prefix} className={groupIndex > 0 ? "mt-3" : ""}>
          <div className="px-3 pb-2">
            <h4 className="text-xs font-semibold text-muted-foreground">
              {prefixLabels[prefix] || prefix}
            </h4>
          </div>
          <div>
            {groupedVariables[prefix].map((variable) => {
              const itemIndex = currentIndex++;
              const isSelected = itemIndex === selectedIndex;
              return (
                <button
                  key={`${prefix}.${variable.name}`}
                  ref={(el) => {
                    itemRefs.current[itemIndex] = el;
                  }}
                  onClick={() => handleSelect(variable, prefix)}
                  className={cn(
                    "w-full px-3 py-2 text-left hover:bg-accent transition-colors flex items-center gap-2",
                    isSelected && "bg-accent"
                  )}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-1 mb-1">
                      <Variable showDefaultValue={false} variable={variable} prefix={prefix} />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
