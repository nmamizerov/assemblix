import { useState, useCallback, useRef, useEffect } from "react";
import { useSelector, useStore } from "react-redux";
import { useAppDispatch, type RootState } from "@/app/store";
import {
  updateNodeStatus,
  setExecutionId,
  setIsExecuting,
  clearNodeStatuses,
} from "../model/editor-mode.slice";
import {
  initializeState,
  resetRuntimeState,
  applyExecutionUpdate,
  selectIsStateDirty,
  selectAgentState,
  selectProjectState,
} from "../model/workflow-runtime-state.slice";
import { selectVariablesByWorkflowId } from "@/entities/workflow/model/variables.slice";
import { useGetProjectQuery } from "@/entities/project";
import type { Workflow } from "@/entities/workflow/model/types";

export interface DebugEvent {
  event_type: string;
  execution_id: string;
  timestamp: string;
  data?: Record<string, unknown>;
  workflow_id?: string;
  session_id?: string;
}

export interface HistoryItem {
  id: string;
  type: "user" | "assistant";
  content?: string;
  events?: DebugEvent[];
}

interface UseWorkflowDebugProps {
  workflow?: Workflow;
  projectId?: string;
}

export const useWorkflowDebug = (props?: UseWorkflowDebugProps) => {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const sessionIdRef = useRef<string | null>(null);
  const clientIdRef = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSessionClosed, setIsSessionClosed] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const dispatch = useAppDispatch();
  const store = useStore<RootState>();

  const { data: project } = useGetProjectQuery(props?.projectId || "", {
    skip: !props?.projectId,
  });

  // Берём актуальную схему переменных из Redux, чтобы реагировать на
  // добавление/удаление переменных без перезагрузки страницы
  const workflowSchema = useSelector((state: RootState) =>
    props?.workflow?.id
      ? selectVariablesByWorkflowId(state, props.workflow.id)
      : [],
  );

  // Синхронизируем agent state с актуальной схемой workflow (merge: новые
  // ключи получают defaults, существующие сохраняются, удалённые исчезают)
  useEffect(() => {
    if (!props?.workflow?.id) return;
    dispatch(initializeState({ workflowSchema }));
  }, [dispatch, props?.workflow?.id, workflowSchema]);

  // То же самое для project state
  useEffect(() => {
    if (!project?.stateSchema) return;
    dispatch(initializeState({ projectSchema: project.stateSchema }));
  }, [dispatch, project?.stateSchema]);

  const clearSession = useCallback(() => {
    setHistory([]);
    sessionIdRef.current = null;
    // Генерируем новый clientId при очистке сессии
    clientIdRef.current = `debug-${crypto.randomUUID()}`;
    setError(null);
    setIsSessionClosed(false);

    dispatch(
      resetRuntimeState({
        workflowSchema,
        projectSchema: project?.stateSchema,
      }),
    );

    dispatch(clearNodeStatuses());
    // Also stop execution if running
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsRunning(false);
    dispatch(setIsExecuting(false));
  }, [dispatch, workflowSchema, project?.stateSchema]);

  const startDebugExecution = useCallback(
    async (workflowId: string, inputMessage: string) => {
      // Генерируем clientId при первом запуске
      if (!clientIdRef.current) {
        clientIdRef.current = `debug-${crypto.randomUUID()}`;
      }

      // Сбрасываем предыдущее состояние только если нет активной сессии
      if (!sessionIdRef.current) {
        setHistory([]);
      }

      // Очищаем статусы нод перед каждым запуском
      dispatch(clearNodeStatuses());

      setError(null);
      setIsRunning(true);
      dispatch(setIsExecuting(true));

      // Добавляем сообщение пользователя и плейсхолдер для ответа ассистента
      const assistantMsgId = crypto.randomUUID();
      setHistory((prev) => [
        ...prev,
        { id: crypto.randomUUID(), type: "user", content: inputMessage },
        { id: assistantMsgId, type: "assistant", events: [] },
      ]);

      // Создаем новый AbortController для возможности отмены
      abortControllerRef.current = new AbortController();

      try {
        const token = localStorage.getItem("accessToken");
        if (!token) {
          throw new Error("Токен авторизации не найден");
        }

        const currentProjectId = props?.projectId || null;
        const headers: Record<string, string> = {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        };

        if (currentProjectId) {
          headers["X-Project-Id"] = currentProjectId;
        }

        // Читаем актуальный state прямо из store, чтобы избежать stale closure
        const rootState = store.getState();
        const isStateDirty = selectIsStateDirty(rootState);
        const agentState = selectAgentState(rootState);
        const projectState = selectProjectState(rootState);

        const response = await fetch(
          `/api/workflows/${workflowId}/execute/debug`,
          {
            method: "POST",
            headers,
            body: JSON.stringify({
              input: {
                message: inputMessage,
              },
              sessionId: sessionIdRef.current, // Используем сохраненный ID сессии
              createSession: true, // Всегда просим создать/использовать сессию для чата
              clientId: clientIdRef.current, // Передаем clientId для ClientSession
              // Передаём state только если пользователь редактировал вручную
              // (иначе backend использует persistent state из chat session)
              state:
                isStateDirty && Object.keys(agentState).length > 0
                  ? agentState
                  : undefined,
              projectState:
                isStateDirty && Object.keys(projectState).length > 0
                  ? projectState
                  : undefined,
            }),
            signal: abortControllerRef.current.signal,
          },
        );

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error("Response body is null");
        }

        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");

          // Оставляем последнюю неполную строку в буфере
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data:")) {
              try {
                const jsonStr = line.slice(5).trim();
                if (!jsonStr) continue;

                const eventData = JSON.parse(jsonStr) as DebugEvent;

                // Добавляем событие в последний элемент истории (ответ ассистента)
                setHistory((prev) => {
                  return prev.map((item) => {
                    if (
                      item.id === assistantMsgId &&
                      item.type === "assistant"
                    ) {
                      return {
                        ...item,
                        events: [...(item.events || []), eventData],
                      };
                    }
                    return item;
                  });
                });

                // Обрабатываем события для обновления статусов нод и runtime state
                switch (eventData.event_type) {
                  case "execution_started":
                    dispatch(setExecutionId(eventData.execution_id));
                    break;

                  case "step_start":
                    if (eventData.data?.node_id) {
                      dispatch(
                        updateNodeStatus({
                          nodeId: eventData.data.node_id as string,
                          status: "running",
                        }),
                      );
                    }
                    break;

                  case "step_complete":
                    if (eventData.data?.node_id) {
                      dispatch(
                        updateNodeStatus({
                          nodeId: eventData.data.node_id as string,
                          status: "completed",
                        }),
                      );
                    }
                    // Real-time обновление state по мере выполнения шагов
                    if (
                      eventData.data?.state_after ||
                      eventData.data?.project_state_after
                    ) {
                      dispatch(
                        applyExecutionUpdate({
                          agentState: eventData.data.state_after as
                            | Record<string, unknown>
                            | undefined,
                          projectState: eventData.data.project_state_after as
                            | Record<string, unknown>
                            | undefined,
                        }),
                      );
                    }
                    break;

                  case "error":
                    if (eventData.data?.failed_node_id) {
                      dispatch(
                        updateNodeStatus({
                          nodeId: eventData.data.failed_node_id as string,
                          status: "error",
                        }),
                      );
                    }
                    setError(
                      (eventData.data?.error_message as string) ||
                        "Произошла ошибка",
                    );
                    break;

                  case "execution_complete":
                    if (eventData?.data?.session_id) {
                      sessionIdRef.current = eventData?.data
                        ?.session_id as string;
                    }
                    if (eventData?.data?.is_session_closed) {
                      setIsSessionClosed(true);
                    }
                    if (
                      eventData?.data?.final_state ||
                      eventData?.data?.final_project_state
                    ) {
                      dispatch(
                        applyExecutionUpdate({
                          agentState: eventData.data.final_state as
                            | Record<string, unknown>
                            | undefined,
                          projectState: eventData.data.final_project_state as
                            | Record<string, unknown>
                            | undefined,
                        }),
                      );
                    }
                    break;
                }

                // Завершаем чтение при финальных событиях
                if (
                  eventData.event_type === "execution_complete" ||
                  eventData.event_type === "error"
                ) {
                  setIsRunning(false);
                  dispatch(setIsExecuting(false));
                  return;
                }
              } catch (parseError) {
                console.error("Error parsing event data:", parseError);
              }
            }
          }
        }
      } catch (err) {
        if (err instanceof Error) {
          if (err.name !== "AbortError") {
            console.error("Error during debug execution:", err);
            setError(err.message);
          }
        }
      } finally {
        setIsRunning(false);
        dispatch(setIsExecuting(false));
      }
    },
    [dispatch, store, props?.projectId],
  );

  const stopExecution = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsRunning(false);
    dispatch(setIsExecuting(false));
  }, [dispatch]);

  const continueSession = useCallback(() => {
    setIsSessionClosed(false);
  }, []);

  return {
    history,
    isRunning,
    error,
    isSessionClosed,
    startDebugExecution,
    stopExecution,
    clearSession,
    continueSession,
  };
};
