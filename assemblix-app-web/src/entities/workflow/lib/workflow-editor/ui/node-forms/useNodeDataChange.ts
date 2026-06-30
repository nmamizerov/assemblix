import { useCallback } from "react";
import { useReactFlow } from "@xyflow/react";

// Хук для обновления данных ноды
export function useNodeDataChange(nodeId: string) {
  const { updateNodeData } = useReactFlow();

  return useCallback(
    (newData: Record<string, unknown>) => {
      // Обновляем данные ноды в ReactFlow СРАЗУ (без дебаунса)
      // Изменения будут автоматически отслежены в canvas.tsx через useEffect
      updateNodeData(nodeId, newData);
    },
    [nodeId, updateNodeData]
  );
}
