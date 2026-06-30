import { MarkerType } from "@xyflow/react";
import type {
  Node as ReactFlowNode,
  Edge as ReactFlowEdge,
} from "@xyflow/react";
import type { Node, Edge, Workflow } from "../../../model/types";
import { NodeType } from "../../../model/types";
import { generateHandleId } from "../helpers/utils";

/**
 * Преобразует ноды из Workflow в формат ReactFlow
 */
export const transformWorkflowNodesToReactFlow = (
  nodes: Node[]
): ReactFlowNode[] => {

  return nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: node.position,
    data: {
      ...node.config
    },
    deletable: node.type !== NodeType.START,
    ...(node.type === NodeType.STICKER && {
      style: {
        width: (node.config as { width?: number }).width ?? 220,
        height: (node.config as { height?: number }).height ?? 160,
      },
    }),
  }));
};

/**
 * Преобразует эджи из Workflow в формат ReactFlow
 */
export const transformWorkflowEdgesToReactFlow = (
  edges: Edge[]
): ReactFlowEdge[] => {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed },
  }));
};

/**
 * Преобразует ноды из ReactFlow обратно в формат Workflow
 */
export const transformReactFlowNodesToWorkflow = (
  nodes: ReactFlowNode[]
): Node[] => {
  return nodes.map((node) => ({
    id: node.id,
    type: node.type as NodeType,
    position: node.position,
    config: node.data,
  })) as Node[];
};

/**
 * Преобразует эджи из ReactFlow обратно в формат Workflow
 */
export const transformReactFlowEdgesToWorkflow = (
  edges: ReactFlowEdge[]
): Edge[] => {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
  }));
};

/**
 * Преобразует состояние ReactFlow в полный объект Workflow
 */
export const transformReactFlowStateToWorkflow = (
  workflow: Workflow,
  nodes: ReactFlowNode[],
  edges: ReactFlowEdge[]
): Workflow => {
  return {
    ...workflow,
    nodes: transformReactFlowNodesToWorkflow(nodes),
    edges: transformReactFlowEdgesToWorkflow(edges),
  };
};

/**
 * Определяет индекс удаленного условия, сравнивая старый и новый массивы conditions
 */
export const findDeletedConditionIndex = (
  oldConditions: { expression: string }[],
  newConditions: { expression: string }[]
): number => {
  // Проходим по старому массиву и ищем элемент, который отсутствует в новом
  for (let i = 0; i < oldConditions.length; i++) {
    // Проверяем, есть ли элемент на позиции i в новом массиве
    if (i >= newConditions.length) {
      // Если новый массив короче, значит удалили с конца
      return i;
    }

    // Сравниваем expression на позиции i
    if (oldConditions[i].expression !== newConditions[i].expression) {
      // Нашли первое несовпадение - это и есть удаленный индекс
      return i;
    }
  }

  // Если не нашли несовпадение, значит удалили последний элемент
  return oldConditions.length - 1;
};

/**
 * Функция для пересоздания edges при изменении количества условий в condition node
 * Реализует "умную перестановку" - edges сдвигаются вниз при удалении условия
 */
export const remapConditionEdges = (
  nodeId: string,
  deletedIndex: number,
  currentEdges: ReactFlowEdge[]
): ReactFlowEdge[] => {
  const updatedEdges: ReactFlowEdge[] = [];

  currentEdges.forEach((edge) => {
    // Обрабатываем только edges, исходящие из измененной ноды
    if (edge.source !== nodeId) {
      updatedEdges.push(edge);
      return;
    }

    // Парсим sourceHandle для извлечения индекса
    // Формат: source_${nodeId}_${index}
    const sourceHandle = edge.sourceHandle;
    if (!sourceHandle) {
      updatedEdges.push(edge);
      return;
    }

    const parts = sourceHandle.split("_");
    const handleIndex = parseInt(parts[parts.length - 1], 10);

    if (isNaN(handleIndex)) {
      updatedEdges.push(edge);
      return;
    }

    // Логика "умной перестановки":
    if (handleIndex < deletedIndex) {
      // Условия до удаленного - оставляем без изменений
      updatedEdges.push(edge);
    } else if (handleIndex === deletedIndex) {
      // Edge от удаленного условия - удаляем (не добавляем в updatedEdges)
      // Ничего не делаем
    } else if (handleIndex > deletedIndex) {
      // Условия после удаленного - сдвигаем индекс вниз на 1
      const newIndex = handleIndex - 1;
      const newSourceHandle = generateHandleId("source", nodeId, newIndex);

      updatedEdges.push({
        ...edge,
        id: `${edge.source}-${newSourceHandle}-${edge.target}`,
        sourceHandle: newSourceHandle,
      });
    }
  });

  return updatedEdges;
};
