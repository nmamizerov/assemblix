import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  addEdge,
  Background,
  MarkerType,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import type {
  Connection,
  Node as ReactFlowNode,
  Edge,
  OnConnectEnd,
  NodeChange,
  EdgeChange,
} from "@xyflow/react";
import { AnimatePresence } from "framer-motion";
import "@xyflow/react/dist/style.css";

import { type Workflow, NodeType } from "../../../model/types";
import { nodeTypes } from "./nodes";
import { WorkflowEditorSidebar } from "./layout/sidebar";
import { StateManagementSidebar } from "./layout/state-management-sidebar";
import { TemplatesPanel } from "./layout/templates-panel";
import { WorkflowEditorHeader } from "./layout/header";
import {
  transformWorkflowNodesToReactFlow,
  transformWorkflowEdgesToReactFlow,
  transformReactFlowStateToWorkflow,
  remapConditionEdges,
  findDeletedConditionIndex,
} from "../model/transforms";
import { WorkflowEditorNodeEditor } from "./layout/nodeEditor";
import { useUpdateWorkflowMutation } from "@/entities/workflow/api/workflow.api";
import { toast } from "sonner";
import { useSelector } from "react-redux";
import {
  selectEditorMode,
  selectNodeStatuses,
  selectAvatarConfig,
  setEditorMode,
  setNodeWarnings,
  setAvatarConfig,
  resetExecution,
} from "../model/editor-mode.slice";
import { analyzeGraph } from "../helpers/graph-analysis";
import { DebugPanel } from "./debug/debug-panel";
import { cn } from "@/shared/lib/utils";
import { useAppDispatch } from "@/app/store";
import type { ExecutionStepResponse } from "@/entities/execution";
import { StepStatus } from "@/entities/execution";
import { useUndoRedo } from "../lib/use-undo-redo";
import { UndoRedoPanel } from "./undo-redo-panel";
import i18n from "@/shared/i18n";

interface WorkflowEditorCanvasProps {
  workflow: Workflow;
  mode?: "edit" | "view";
  executionSteps?: ExecutionStepResponse[];
  onNodeClick?: (nodeId: string) => void;
  onRefetch?: () => void;
  onLoadVersion?: (versionId: string) => void;
  onCanvasChange?: () => void;
  isDraft?: boolean;
}

// Функция для создания дефолтного конфига для новой ноды
const getDefaultNodeConfig = (type: NodeType): Record<string, unknown> => {
  switch (type) {
    case NodeType.START:
      return {};
    case NodeType.AGENT:
      return {
        name: i18n.t("workflow.nodeDefaults.agentName"),
        provider: "openai",
        model: "gpt-4.1-nano",
        credentialId: "",
        instructions: [{ role: "user", content: "" }],
      };
    case NodeType.CONDITION:
      return {
        conditions: [{ expression: "" }],
      };
    case NodeType.SET_VARIABLE:
      return {
        updates: [],
      };
    case NodeType.END:
      return {
        name: i18n.t("workflow.nodeDefaults.endName"),
        properties: { status: "success" },
      };
    case NodeType.STICKER:
      return {
        text: "",
      };
    case NodeType.HTTP_REQUEST:
      return {
        url: "",
        method: "GET",
        headers: {},
        timeout: 30,
      };
    default:
      return {};
  }
};

// Генератор уникального ID для ноды
let nodeIdCounter = 0;
const generateNodeId = () => {
  nodeIdCounter += 1;
  return `node-${Date.now()}-${nodeIdCounter}`;
};

const FlowCanvas = ({
  workflow,
  onSaveWorkflow,
  viewMode = "edit",
  executionSteps,
  onNodeClick,
  onRefetch,
  onLoadVersion,
  onCanvasChange,
  isDraft,
}: {
  workflow: Workflow;
  onSaveWorkflow: (workflow: Workflow) => void;
  viewMode?: "edit" | "view";
  executionSteps?: ExecutionStepResponse[];
  onNodeClick?: (nodeId: string) => void;
  onRefetch?: () => void;
  onLoadVersion?: (versionId: string) => void;
  onCanvasChange?: () => void;
  isDraft?: boolean;
}) => {
  const mode = useSelector(selectEditorMode);
  const nodeStatuses = useSelector(selectNodeStatuses);
  const isDebugMode = mode === "DEBUG";
  const isViewMode = viewMode === "view";
  const dispatch = useAppDispatch();

  // Seed the session avatar config ONCE per loaded workflow. The slice is the
  // source of truth afterwards (header updates it optimistically); depending on
  // workflow.config.avatar would re-clobber a freshly-picked voice whenever a
  // node edit rebuilds the (stale-avatar) workflow prop.
  useEffect(() => {
    dispatch(setAvatarConfig(workflow.config?.avatar ?? null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow.id, dispatch]);

  // State для временной ноды
  const [tempNodeId, setTempNodeId] = useState<string | null>(null);
  const [isSidebarHighlighted, setIsSidebarHighlighted] = useState(false);
  const [isTemplatesPanelOpen, setIsTemplatesPanelOpen] = useState(false);

  // Преобразуем данные из workflow в формат ReactFlow
  const initialNodes = useMemo(() => {
    const nodes = transformWorkflowNodesToReactFlow(workflow.nodes);

    if (isViewMode && executionSteps) {
      const stepsByNodeId = new Map(
        executionSteps.map((step) => [step.nodeId, step]),
      );

      return nodes.map((node) => {
        const step = stepsByNodeId.get(node.id);

        if (!step) {
          return {
            ...node,
            className: cn(node.className, "node-debug-inactive"),
          };
        }

        return {
          ...node,
          className: cn(
            node.className,
            step.status === StepStatus.COMPLETED && "node-completed",
            step.status === StepStatus.FAILED && "node-error",
            step.status === StepStatus.RUNNING && "node-running",
          ),
        };
      });
    }

    return nodes;
  }, [workflow.nodes, isViewMode, executionSteps]);

  const initialEdges = useMemo(
    () => transformWorkflowEdgesToReactFlow(workflow.edges),
    [workflow.edges],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { screenToFlowPosition, getNodes, getEdges } = useReactFlow();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<number | null>(null);
  const positionDebounceRef = useRef<number | null>(null);
  const isDraggingRef = useRef(false);
  const isInitialMount = useRef(true);
  const previousNodesRef = useRef<ReactFlowNode[]>(initialNodes);
  const isProgrammaticUpdate = useRef(false);
  const previousWorkflowNodesRef = useRef(workflow.nodes);

  // Буфер обмена для copy/paste
  const clipboardRef = useRef<{
    nodes: ReactFlowNode[];
    edges: Edge[];
  } | null>(null);

  // Инициализация undo/redo
  const { undo, redo, takeSnapshot, canUndo, canRedo } = useUndoRedo(
    setNodes,
    setEdges,
  );

  // Применяем статусы нод в debug режиме или view режиме
  useEffect(() => {
    if (isDebugMode) {
      setNodes((nds) =>
        nds.map((node) => {
          const status = nodeStatuses[node.id];
          const baseClassName = node.className
            ?.replace(/node-(running|completed|error|debug-inactive)/g, "")
            .trim();

          return {
            ...node,
            className: cn(
              baseClassName,
              !status && "node-debug-inactive",
              status === "running" && "node-running",
              status === "completed" && "node-completed",
              status === "error" && "node-error",
            ),
          };
        }),
      );
    } else if (isViewMode && executionSteps) {
      // Применяем статусы из executionSteps в режиме просмотра
      const stepsByNodeId = new Map(
        executionSteps.map((step) => [step.nodeId, step]),
      );

      setNodes((nds) =>
        nds.map((node) => {
          const step = stepsByNodeId.get(node.id);
          const baseClassName = node.className
            ?.replace(/node-(running|completed|error|debug-inactive)/g, "")
            .trim();

          if (!step) {
            return {
              ...node,
              className: cn(baseClassName, "node-debug-inactive"),
            };
          }

          return {
            ...node,
            className: cn(
              baseClassName,
              step.status === StepStatus.COMPLETED && "node-completed",
              step.status === StepStatus.FAILED && "node-error",
              step.status === StepStatus.RUNNING && "node-running",
            ),
          };
        }),
      );
    } else {
      // Очищаем классы статусов при выходе из debug/view режима
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          className: node.className
            ?.replace(/node-(running|completed|error|debug-inactive)/g, "")
            .trim(),
        })),
      );
    }
  }, [isDebugMode, isViewMode, nodeStatuses, executionSteps, setNodes]);

  // Статический анализ графа (только в режиме редактирования): подсвечиваем ноды с
  // потенциальными проблемами параллельного выполнения — несколько END в параллельных
  // ветках или join на цикле. Пересчитываем только при изменении СТРУКТУРЫ графа
  // (id/type нод и source/target рёбер), а не при перетаскивании.
  const graphSignature = useMemo(
    () =>
      JSON.stringify([
        nodes.map((n) => [n.id, n.type]),
        edges.map((e) => [e.source, e.target]),
      ]),
    [nodes, edges],
  );

  useEffect(() => {
    if (isDebugMode || isViewMode) {
      dispatch(setNodeWarnings({}));
      return;
    }
    dispatch(setNodeWarnings(analyzeGraph(getNodes(), getEdges())));
    // graphSignature captures the structural inputs; getNodes/getEdges are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphSignature, isDebugMode, isViewMode, dispatch]);

  // Обработчик копирования выбранных нод
  const handleCopy = useCallback(() => {
    if (isDebugMode || isViewMode) return;

    const selectedNodes = getNodes().filter(
      (node) => node.selected && node.type !== NodeType.START,
    );
    if (selectedNodes.length === 0) return;

    const selectedNodeIds = new Set(selectedNodes.map((node) => node.id));

    // Получаем edges между выбранными нодами
    const selectedEdges = getEdges().filter(
      (edge) =>
        selectedNodeIds.has(edge.source) && selectedNodeIds.has(edge.target),
    );

    clipboardRef.current = {
      nodes: JSON.parse(JSON.stringify(selectedNodes)),
      edges: JSON.parse(JSON.stringify(selectedEdges)),
    };
  }, [getNodes, getEdges, isDebugMode, isViewMode]);

  // Обработчик вставки скопированных нод
  const handlePaste = useCallback(() => {
    if (isDebugMode || isViewMode || !clipboardRef.current) return;

    const { nodes: copiedNodes, edges: copiedEdges } = clipboardRef.current;
    const pasteNodes = copiedNodes.filter(
      (node) => node.type !== NodeType.START,
    );
    if (pasteNodes.length === 0) return;

    // Создаем snapshot для undo (используем nodes/edges из замыкания)
    takeSnapshot(nodes, edges);

    // Создаем map старых ID -> новых ID
    const idMap = new Map<string, string>();
    pasteNodes.forEach((node) => {
      idMap.set(node.id, generateNodeId());
    });

    // Создаем новые ноды со смещением позиции
    const newNodes: ReactFlowNode[] = pasteNodes.map((node) => ({
      ...node,
      id: idMap.get(node.id)!,
      position: {
        x: node.position.x + 20,
        y: node.position.y + 20,
      },
      selected: true,
    }));

    // Создаем новые edges с обновленными ID
    const newEdges: Edge[] = copiedEdges
      .filter((edge) => idMap.has(edge.source) && idMap.has(edge.target))
      .map((edge) => ({
        ...edge,
        id: `${idMap.get(edge.source)}-${idMap.get(edge.target)}-${Date.now()}`,
        source: idMap.get(edge.source)!,
        target: idMap.get(edge.target)!,
      }));

    // Снимаем выделение с существующих нод и добавляем вставленные выделенными
    setNodes((nds) => [
      ...nds.map((n) => ({ ...n, selected: false })),
      ...newNodes,
    ]);
    setEdges((eds) => [...eds, ...newEdges]);
  }, [nodes, edges, setNodes, setEdges, takeSnapshot, isDebugMode, isViewMode]);

  // Обработчик клавиатурных шорткатов для undo/redo
  useEffect(() => {
    // Не активируем шорткаты в debug или view режиме
    if (isDebugMode || isViewMode) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      // Проверяем, что фокус не на input/textarea
      const target = event.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }

      const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
      const ctrlKey = isMac ? event.metaKey : event.ctrlKey;

      // Ctrl+C (Cmd+C на Mac) - Copy
      if (ctrlKey && event.key === "c") {
        event.preventDefault();
        handleCopy();
      }
      // Ctrl+V (Cmd+V на Mac) - Paste
      else if (ctrlKey && event.key === "v") {
        event.preventDefault();
        handlePaste();
      }
      // Ctrl+Z (Cmd+Z на Mac) - Undo
      else if (ctrlKey && event.key === "z" && !event.shiftKey) {
        event.preventDefault();
        undo();
      }
      // Ctrl+Shift+Z (Cmd+Shift+Z на Mac) или Ctrl+Y - Redo
      else if (
        (ctrlKey && event.key === "z" && event.shiftKey) ||
        (ctrlKey && event.key === "y")
      ) {
        event.preventDefault();
        redo();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      // Очищаем таймер дебаунса позиции при размонтировании
      if (positionDebounceRef.current) {
        clearTimeout(positionDebounceRef.current);
      }
    };
  }, [isDebugMode, isViewMode, undo, redo, handleCopy, handlePaste]);

  // Обновляем ноды и эджи при изменении workflow (не в режиме просмотра)
  useEffect(() => {
    // В режиме просмотра не обновляем ноды при изменении workflow
    // так как это сбрасывает примененные статусы
    if (isViewMode) return;

    // Проверяем, изменились ли фактические данные нод
    // Если изменился только isDraft, но данные те же - не обновляем
    if (previousWorkflowNodesRef.current === workflow.nodes) {
      return;
    }

    // Сохраняем ссылку на текущие ноды
    previousWorkflowNodesRef.current = workflow.nodes;

    // Устанавливаем флаг программного обновления
    isProgrammaticUpdate.current = true;
    setNodes(transformWorkflowNodesToReactFlow(workflow.nodes));
    setEdges(transformWorkflowEdgesToReactFlow(workflow.edges));
    // Сбрасываем флаг через таймаут (после того как React Flow обработает изменения)
    setTimeout(() => {
      isProgrammaticUpdate.current = false;
    }, 100);
  }, [workflow, setNodes, setEdges, isViewMode, isDraft]);

  // Отслеживаем изменения в condition nodes для обновления edges
  useEffect(() => {
    // Пропускаем первый рендер
    if (isInitialMount.current) {
      return;
    }

    const previousNodes = previousNodesRef.current;

    // Проверяем каждую ноду на изменения
    nodes.forEach((currentNode) => {
      // Обрабатываем только CONDITION ноды
      if (currentNode.type !== NodeType.CONDITION) {
        return;
      }

      // Находим предыдущее состояние этой ноды
      const previousNode = previousNodes.find((n) => n.id === currentNode.id);
      if (!previousNode) {
        return;
      }

      // Получаем массивы conditions
      const oldConditions = (previousNode.data?.conditions || []) as {
        expression: string;
      }[];
      const newConditions = (currentNode.data?.conditions || []) as {
        expression: string;
      }[];

      // Проверяем, изменилось ли количество условий (удаление)
      if (
        newConditions.length < oldConditions.length &&
        oldConditions.length > 0
      ) {
        // Определяем индекс удаленного условия
        const deletedIndex = findDeletedConditionIndex(
          oldConditions,
          newConditions,
        );

        // Пересоздаем edges с учетом удаления
        const updatedEdges = remapConditionEdges(
          currentNode.id,
          deletedIndex,
          edges,
        );

        // Обновляем edges
        setEdges(updatedEdges);
      }
    });

    // Обновляем ref с текущим состоянием nodes
    previousNodesRef.current = nodes;
  }, [nodes, edges, setEdges]);

  // Обертки для сохранения истории изменений
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      if (!isDebugMode && !isViewMode && changes.length > 0) {
        // Игнорируем изменения dimensions и select - они не являются реальными правками пользователя
        const significantChanges = changes.filter(
          (change) => change.type !== "dimensions" && change.type !== "select",
        );

        // Если остались только незначительные изменения, не уведомляем
        const hasSignificantChanges = significantChanges.length > 0;

        // Проверяем типы изменений среди значимых
        const hasAddOrRemove = significantChanges.some(
          (change) => change.type === "add" || change.type === "remove",
        );
        const hasPosition = significantChanges.some(
          (change) => change.type === "position",
        );

        // Для добавления/удаления делаем snapshot сразу
        if (hasAddOrRemove) {
          takeSnapshot(nodes, edges);
        }
        // Для перемещения: snapshot только в начале драга
        else if (hasPosition) {
          // Если это первое перемещение - делаем snapshot
          if (!isDraggingRef.current) {
            // Используем nodes/edges из замыкания - состояние ДО применения changes!
            takeSnapshot(nodes, edges);
            isDraggingRef.current = true;
          }

          // Очищаем предыдущий таймер
          if (positionDebounceRef.current) {
            clearTimeout(positionDebounceRef.current);
          }
          // Устанавливаем таймер для сброса флага драга
          positionDebounceRef.current = window.setTimeout(() => {
            isDraggingRef.current = false;
          }, 500);
        }

        // Уведомляем только о значимых изменениях и не во время программного обновления
        if (
          onCanvasChange &&
          hasSignificantChanges &&
          !isProgrammaticUpdate.current
        ) {
          onCanvasChange();
        }
      }
      onNodesChange(changes);
    },
    [
      nodes,
      edges,
      takeSnapshot,
      onNodesChange,
      isDebugMode,
      isViewMode,
      onCanvasChange,
    ],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (!isDebugMode && !isViewMode && changes.length > 0) {
        // Сохраняем snapshot только для добавления/удаления edges
        const hasAddOrRemove = changes.some(
          (change) => change.type === "add" || change.type === "remove",
        );
        if (hasAddOrRemove) {
          // Используем nodes/edges из замыкания - состояние ДО применения changes!
          takeSnapshot(nodes, edges);
        }

        // Уведомляем о любых изменениях на canvas
        if (onCanvasChange) {
          onCanvasChange();
        }
      }
      onEdgesChange(changes);
    },
    [
      nodes,
      edges,
      takeSnapshot,
      onEdgesChange,
      isDebugMode,
      isViewMode,
      onCanvasChange,
    ],
  );

  // Запрет соединения ноды с самой собой: узел не может быть собственной
  // следующей нодой (иначе исполнитель зациклится на нём до кап-лимита).
  const isValidConnection = useCallback(
    (connection: Connection | Edge) => connection.source !== connection.target,
    [],
  );

  const onConnect = useCallback(
    (params: Connection) => {
      // Страховка на случай программного добавления ребра в обход isValidConnection.
      if (params.source === params.target) {
        return;
      }
      if (!isDebugMode && !isViewMode) {
        // Используем nodes/edges из замыкания - состояние ДО подключения!
        takeSnapshot(nodes, edges);
      }
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            animated: false,
            markerEnd: { type: MarkerType.ArrowClosed },
          },
          eds,
        ),
      );
    },
    [setEdges, nodes, edges, takeSnapshot, isDebugMode, isViewMode],
  );

  // Обработчик завершения соединения (успешного или неуспешного)
  const onConnectEnd: OnConnectEnd = useCallback(
    (event, connectionState) => {
      // Если соединение неуспешное (isValid === false или null) и не в debug режиме, создаем временную ноду
      if (
        connectionState.isValid !== true &&
        !isDebugMode &&
        connectionState.fromNode
      ) {
        // Получаем координаты
        const { clientX, clientY } =
          "changedTouches" in event ? event.changedTouches[0] : event;

        // Создаем временную ноду в месте отпускания
        const tempId = generateNodeId();
        const position = screenToFlowPosition({ x: clientX, y: clientY });

        // Валидация координат
        if (isNaN(position.x) || isNaN(position.y)) {
          return;
        }

        const tempNode: ReactFlowNode = {
          id: tempId,
          type: "placeholder",
          position,
          data: { label: "Новый элемент" },
          deletable: false,
        };

        // Создаем edge от исходной ноды к временной
        const tempEdge = {
          id: `temp-${tempId}`,
          source: connectionState.fromNode.id,
          sourceHandle: connectionState.fromHandle?.id || null,
          target: tempId,
          animated: false,
          markerEnd: { type: MarkerType.ArrowClosed },
        };

        // Оборачиваем обновление в setTimeout, чтобы дать React Flow время очистить линию соединения
        setTimeout(() => {
          // 1. Обновляем локальный стейт
          const newNodes = [...nodes, tempNode];
          const newEdges = [...edges, tempEdge];

          setNodes(newNodes);
          setEdges(newEdges);
          setTempNodeId(tempId);
          setIsSidebarHighlighted(true); // Включаем подсветку

          // 2. СРАЗУ обновляем workflow через бэкенд
          const updatedWorkflow = transformReactFlowStateToWorkflow(
            workflow,
            newNodes,
            newEdges,
          );
          onSaveWorkflow(updatedWorkflow);
        }, 10);
      }
    },
    [
      screenToFlowPosition,
      isDebugMode,
      setNodes,
      setEdges,
      nodes,
      edges,
      workflow,
      onSaveWorkflow,
    ],
  );

  // Обработчик завершения соединения (успешного или неуспешного)
  // Callback для изменений workflow (будет вызываться с дебаунсом)
  const handleWorkflowChange = useCallback(
    (updatedWorkflow: Workflow) => {
      onSaveWorkflow(updatedWorkflow);
    },
    [onSaveWorkflow],
  );

  // Отслеживаем изменения в nodes и edges и вызываем handleWorkflowChange с дебаунсом
  useEffect(() => {
    // Пропускаем первый рендер, чтобы не вызывать callback при инициализации
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    // Не сохраняем в debug режиме или view режиме
    if (isDebugMode || isViewMode) {
      return;
    }

    // Не сохраняем при программном обновлении (загрузка версий, загрузка данных и т.д.)
    if (isProgrammaticUpdate.current) {
      return;
    }

    // Очищаем предыдущий таймер
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Устанавливаем новый таймер на 200мс
    debounceTimerRef.current = window.setTimeout(() => {
      // Формируем полный Workflow объект из текущего состояния ReactFlow
      const updatedWorkflow = transformReactFlowStateToWorkflow(
        workflow,
        nodes,
        edges,
      );

      // Вызываем callback
      handleWorkflowChange(updatedWorkflow);
    }, 200);

    // Очищаем таймер при размонтировании
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [
    nodes,
    edges,
    workflow,
    handleWorkflowChange,
    isDebugMode,
    isViewMode,
    isDraft,
  ]);

  // Обработка drop события для добавления новой ноды
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      // Не добавляем ноды в debug режиме или view режиме
      if (isDebugMode || isViewMode) return;

      // Проверяем, это обычная нода или шаблон
      const type = event.dataTransfer.getData(
        "application/reactflow",
      ) as NodeType;
      const templateConfigStr = event.dataTransfer.getData(
        "application/reactflow-template",
      );

      if (!type && !templateConfigStr) return;

      // Преобразуем координаты экрана в координаты flow
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      // Сохраняем snapshot перед добавлением ноды (используем nodes/edges из замыкания)
      takeSnapshot(nodes, edges);

      if (templateConfigStr) {
        // Создаем ноду из шаблона
        try {
          const templateConfig = JSON.parse(templateConfigStr);
          const newNode: ReactFlowNode = {
            id: generateNodeId(),
            type: templateConfig.type,
            position,
            data: templateConfig.config,
            deletable: templateConfig.type !== NodeType.START,
          };
          setNodes((nds) => nds.concat(newNode));
        } catch (error) {
          console.error("Failed to parse template config:", error);
          toast.error("Не удалось загрузить шаблон");
        }
      } else {
        // Создаем новую ноду из сайдбара
        const newNode: ReactFlowNode = {
          id: generateNodeId(),
          type,
          position,
          data: getDefaultNodeConfig(type),
          deletable: type !== NodeType.START,
        };
        setNodes((nds) => nds.concat(newNode));
      }
    },
    [
      screenToFlowPosition,
      setNodes,
      isDebugMode,
      isViewMode,
      takeSnapshot,
      nodes,
      edges,
    ],
  );

  // Обработчик выбора типа ноды из сайдбара
  // Обработчик переключения панели шаблонов
  const handleTemplatesToggle = useCallback(() => {
    setIsTemplatesPanelOpen((prev) => !prev);
  }, []);

  // Обработчик выбора типа ноды из сайдбара
  const handleNodeTypeSelect = useCallback(
    (nodeType: NodeType | string) => {
      if (!tempNodeId) return;

      // Найти временную ноду
      const tempNode = nodes.find((n) => n.id === tempNodeId);
      if (!tempNode) return;

      // Сохраняем snapshot (временная нода уже была добавлена с snapshot в onConnectEnd)
      // Здесь не нужен дополнительный snapshot, так как это замена типа временной ноды

      // Заменить временную ноду на выбранный тип
      const updatedNodes = nodes.map((n) =>
        n.id === tempNodeId
          ? {
              ...n,
              type: nodeType,
              data: getDefaultNodeConfig(nodeType as NodeType),
              deletable: nodeType !== NodeType.START,
            }
          : n,
      );

      setNodes(updatedNodes);

      // Сохраняем изменения в workflow
      const updatedWorkflow = transformReactFlowStateToWorkflow(
        workflow,
        updatedNodes,
        edges,
      );
      onSaveWorkflow(updatedWorkflow);

      // Сбросить состояние
      setTempNodeId(null);
      setIsSidebarHighlighted(false);
    },
    [tempNodeId, nodes, edges, setNodes, workflow, onSaveWorkflow],
  );

  // Обработчик клика на ноду в view режиме
  const handleNodeClickInternal = useCallback(
    (_event: React.MouseEvent, node: ReactFlowNode) => {
      if (isViewMode && onNodeClick) {
        onNodeClick(node.id);
      }
    },
    [isViewMode, onNodeClick],
  );

  // Обработчик клика на рабочую область (не на ноды)
  const handlePaneClick = useCallback(() => {
    if (tempNodeId) {
      setNodes((nds) => nds.filter((n) => n.id !== tempNodeId));
      setEdges((eds) => eds.filter((e) => e.target !== tempNodeId));
      setTempNodeId(null);
      setIsSidebarHighlighted(false);
      return;
    }

    if (isDebugMode) {
      dispatch(setEditorMode("EDIT"));
      dispatch(resetExecution());
    }

    // В view режиме закрываем drawer при клике на пустую область
    if (isViewMode && onNodeClick) {
      onNodeClick("");
    }
  }, [
    isDebugMode,
    isViewMode,
    dispatch,
    tempNodeId,
    setNodes,
    setEdges,
    onNodeClick,
  ]);

  return (
    <div ref={reactFlowWrapper} className="flex-1 h-full w-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={
          isDebugMode || isViewMode ? undefined : handleNodesChange
        }
        onEdgesChange={
          isDebugMode || isViewMode ? undefined : handleEdgesChange
        }
        onConnect={isDebugMode || isViewMode ? undefined : onConnect}
        onConnectEnd={isDebugMode || isViewMode ? undefined : onConnectEnd}
        isValidConnection={isValidConnection}
        onDrop={isDebugMode || isViewMode ? undefined : onDrop}
        onDragOver={isDebugMode || isViewMode ? undefined : onDragOver}
        onPaneClick={handlePaneClick}
        onNodeClick={handleNodeClickInternal}
        nodeTypes={nodeTypes}
        fitView
        className="bg-canvas"
        nodesDraggable={!isDebugMode && !isViewMode}
        deleteKeyCode={["Delete", "Backspace"]}
        nodesConnectable={!isDebugMode && !isViewMode}
        elementsSelectable={!isDebugMode && !isViewMode}
        defaultEdgeOptions={{
          type: "default",
          animated: false,
          markerEnd: { type: MarkerType.ArrowClosed },
        }}
      >
        <Background color="var(--border)" gap={16} />
        <AnimatePresence mode="wait">
          {!isDebugMode && !isViewMode && (
            <WorkflowEditorSidebar
              key="nodes-sidebar"
              isHighlighted={isSidebarHighlighted}
              onNodeTypeSelect={handleNodeTypeSelect}
              onTemplatesClick={handleTemplatesToggle}
              isTemplatesPanelOpen={isTemplatesPanelOpen}
            />
          )}
          {isDebugMode && !isViewMode && (
            <StateManagementSidebar
              key="state-sidebar"
              workflow={workflow}
            />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {!isDebugMode && !isViewMode && (
            <TemplatesPanel
              key="templates-panel"
              isOpen={isTemplatesPanelOpen}
              onClose={() => setIsTemplatesPanelOpen(false)}
            />
          )}
        </AnimatePresence>
        {!isViewMode && (
          <WorkflowEditorHeader
            workflow={workflow}
            onRefetch={onRefetch}
            onLoadVersion={onLoadVersion}
            isDraft={isDraft}
          />
        )}
        <AnimatePresence>
          {!isDebugMode && !isViewMode && (
            <WorkflowEditorNodeEditor key="node-editor" workflow={workflow} />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {isDebugMode && <DebugPanel key="debug-panel" workflow={workflow} />}
        </AnimatePresence>
        <AnimatePresence>
          {!isDebugMode && !isViewMode && (
            <UndoRedoPanel
              key="undo-redo-panel"
              onUndo={undo}
              onRedo={redo}
              canUndo={canUndo}
              canRedo={canRedo}
            />
          )}
        </AnimatePresence>
      </ReactFlow>
    </div>
  );
};

export const WorkflowEditorCanvas = ({
  workflow,
  mode = "edit",
  executionSteps,
  onNodeClick,
  onRefetch,
  onLoadVersion,
  onCanvasChange,
  isDraft,
}: WorkflowEditorCanvasProps) => {
  const [updateWorkflow] = useUpdateWorkflowMutation();
  // The workflow prop's config.avatar is stale (updateWorkflow doesn't refetch it),
  // so any node-edit save must carry the live avatar config from the slice —
  // otherwise it would overwrite a freshly-picked voice with the loaded-time one.
  const avatarConfig = useSelector(selectAvatarConfig);

  const onSaveWorkflow = useCallback(
    async (updatedWorkflow: Workflow) => {
      // В режиме просмотра не сохраняем
      if (mode === "view") return;

      const response = await updateWorkflow({
        ...updatedWorkflow,
        config: { ...updatedWorkflow.config, avatar: avatarConfig ?? undefined },
        state: undefined,
      });
      if (response.error) {
        toast.error("Ошибка сохранения агента");
      }
    },
    [updateWorkflow, mode, avatarConfig],
  );

  return (
    <div className="w-full h-screen bg-canvas overflow-hidden border-t border-border">
      <ReactFlowProvider>
        <FlowCanvas
          workflow={workflow}
          onSaveWorkflow={onSaveWorkflow}
          viewMode={mode}
          executionSteps={executionSteps}
          onNodeClick={onNodeClick}
          onRefetch={onRefetch}
          onLoadVersion={onLoadVersion}
          onCanvasChange={onCanvasChange}
          isDraft={isDraft}
        />
      </ReactFlowProvider>
    </div>
  );
};
