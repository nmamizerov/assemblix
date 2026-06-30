import { useCallback, useRef, useState } from "react";
import type { Node as ReactFlowNode, Edge } from "@xyflow/react";

interface HistoryState {
  nodes: ReactFlowNode[];
  edges: Edge[];
}

interface UseUndoRedoReturn {
  undo: () => void;
  redo: () => void;
  takeSnapshot: (nodes: ReactFlowNode[], edges: Edge[]) => void;
  canUndo: boolean;
  canRedo: boolean;
}

const MAX_HISTORY_SIZE = 50;

export const useUndoRedo = (
  setNodes: (
    nodes: ReactFlowNode[] | ((nodes: ReactFlowNode[]) => ReactFlowNode[])
  ) => void,
  setEdges: (edges: Edge[] | ((edges: Edge[]) => Edge[])) => void
): UseUndoRedoReturn => {
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const past = useRef<HistoryState[]>([]);
  const future = useRef<HistoryState[]>([]);
  const lastSnapshotTime = useRef<number>(0);

  const takeSnapshot = useCallback((nodes: ReactFlowNode[], edges: Edge[]) => {
    // Дедупликация: не сохраняем snapshot, если предыдущий был меньше 100мс назад
    // и имел такое же количество элементов (защита от двойных вызовов при удалении/добавлении)
    const now = Date.now();
    if (past.current.length > 0 && now - lastSnapshotTime.current < 100) {
      const lastSnapshot = past.current[past.current.length - 1];
      if (
        lastSnapshot.nodes.length === nodes.length &&
        lastSnapshot.edges.length === edges.length
      ) {
        return;
      }
    }

    lastSnapshotTime.current = now;

    // Сохраняем текущее состояние в историю
    past.current.push({
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    });

    // Ограничиваем размер истории
    if (past.current.length > MAX_HISTORY_SIZE) {
      past.current.shift();
    }

    // При новом действии очищаем future (redo)
    future.current = [];

    setCanUndo(past.current.length > 0);
    setCanRedo(false);
  }, []);

  const undo = useCallback(() => {
    if (past.current.length === 0) return;

    const lastState = past.current.pop();
    if (!lastState) return;

    // Сохраняем текущее состояние ОДИН РАЗ с помощью колбэка
    let currentNodesSnapshot: ReactFlowNode[] = [];
    let currentEdgesSnapshot: Edge[] = [];

    setNodes((currentNodes) => {
      currentNodesSnapshot = currentNodes;
      return currentNodes; // Возвращаем без изменений для получения состояния
    });

    setEdges((currentEdges) => {
      currentEdgesSnapshot = currentEdges;
      return currentEdges; // Возвращаем без изменений для получения состояния
    });

    // Сохраняем текущее состояние в future
    future.current.push({
      nodes: JSON.parse(JSON.stringify(currentNodesSnapshot)),
      edges: JSON.parse(JSON.stringify(currentEdgesSnapshot)),
    });

    // Применяем восстановленное состояние ПРЯМЫМИ вызовами
    setNodes(lastState.nodes);
    setEdges(lastState.edges);

    setCanUndo(past.current.length > 0);
    setCanRedo(true);
  }, [setNodes, setEdges]);

  const redo = useCallback(() => {
    if (future.current.length === 0) return;

    const nextState = future.current.pop();
    if (!nextState) return;

    // Сохраняем текущее состояние ОДИН РАЗ с помощью колбэка
    let currentNodesSnapshot: ReactFlowNode[] = [];
    let currentEdgesSnapshot: Edge[] = [];

    setNodes((currentNodes) => {
      currentNodesSnapshot = currentNodes;
      return currentNodes; // Возвращаем без изменений для получения состояния
    });

    setEdges((currentEdges) => {
      currentEdgesSnapshot = currentEdges;
      return currentEdges; // Возвращаем без изменений для получения состояния
    });

    // Сохраняем текущее состояние в past
    past.current.push({
      nodes: JSON.parse(JSON.stringify(currentNodesSnapshot)),
      edges: JSON.parse(JSON.stringify(currentEdgesSnapshot)),
    });

    // Применяем восстановленное состояние ПРЯМЫМИ вызовами
    setNodes(nextState.nodes);
    setEdges(nextState.edges);

    setCanUndo(true);
    setCanRedo(future.current.length > 0);
  }, [setNodes, setEdges]);

  return {
    undo,
    redo,
    takeSnapshot,
    canUndo,
    canRedo,
  };
};
