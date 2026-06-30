import { useMemo } from "react";
import { useStore } from "@xyflow/react";

/**
 * Хук для проверки доступности handle для подключения.
 * Реактивно отслеживает изменения edges через useStore.
 *
 * @param nodeId - ID ноды
 * @param handleId - ID handle (опционально)
 * @returns isConnectable - можно ли подключить новое соединение к этому handle
 */
export function useHandleConnectivity(nodeId: string, handleId?: string) {
  // Создаем мемоизированный селектор для конкретного handle
  const selector = useMemo(
    () =>
      (state: {
        edges: Array<{ source: string; sourceHandle?: string | null }>;
      }) => {
        // Проверяем, есть ли исходящее ребро из этого handle
        return state.edges.some(
          (edge) =>
            edge.source === nodeId &&
            (handleId ? edge.sourceHandle === handleId : true)
        );
      },
    [nodeId, handleId]
  );

  // useStore подписывается на изменения и вызывает ре-рендер
  const hasConnection = useStore(selector);

  return !hasConnection; // возвращаем isConnectable
}
