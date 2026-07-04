export interface WorkflowVersion {
  id: string;
  version: number;
  createdAt: string;
  isActive: boolean;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string | null;
  isActive: boolean;
  isPublished: boolean;
  isTemplate: boolean;
  version?: number | null;
  publishedForWorkflowId?: string | null;
  createdAt: string;
  updatedAt: string;
  nodes: Node[];
  edges: Edge[];
  state?: StateVariable[];
  versions?: WorkflowVersion[];
}

export enum NodeType {
  START = "start",
  AGENT = "agent",
  CONDITION = "condition",
  SET_VARIABLE = "set_variable",
  END = "end",
  STICKER = "sticker",
  HTTP_REQUEST = "http_request",
  PLACEHOLDER = "placeholder", // Временный тип
}

// Конфигурации узлов

export type StartNodeConfig = {
  firstPhrase?: string;
};

export enum Role {
  SYSTEM = "system",
  USER = "user",
  ASSISTANT = "assistant",
}
export interface Instructions {
  role: Role;
  content: string;
}

export enum Provider {
  OPENAI = "openai",
  GEMINI = "gemini",
  DEEPSEEK = "deepseek",
}

export interface FallbackModelConfig {
  provider: Provider;
  model: string;
  credentialId?: string;
}

export interface AgentNodeConfig {
  // Базовые обязательные поля
  name: string;
  provider: Provider;
  model: string;
  instructions: Instructions[];
  credentialId: string;

  // Динамические поля, специфичные для провайдера
  // OpenAI: temperature, max_tokens, top_p, frequency_penalty, presence_penalty, responseFormat
  // Gemini: temperature, top_p, top_k, max_output_tokens, safety_settings, stop_sequences

  // JSON Schema для структурированного вывода
  responseFormat?: "text" | "json_object";
  responseSchema?: Record<string, unknown>;

  // Список инструментов
  tools?: string[]; // Список названий инструментов, например ["web_search"]

  // Базы знаний
  knowledgeBaseIds?: string[];

  // Отправка истории чата в LLM
  includeChatHistory?: boolean;

  // --- Надёжность (Фаза 3): ретраи / фолбэки / таймаут ---
  // Фолбэк-модели: пробуются по порядку, когда основная исчерпала transient-ретраи.
  fallbackModels?: FallbackModelConfig[];
  // Потолок на весь агентский цикл ноды (секунды). Пусто → дефолт из настроек.
  timeoutSeconds?: number;
  // Сколько раз ретраить transient-сбой одного LLM-вызова. Пусто → дефолт из настроек.
  maxRetries?: number;
  // Жёсткий таймаут на последней модели цепочки. Дефолт true.
  enforceTimeoutOnLast?: boolean;

  // --- Контроль контекста ---
  // Класть ли ответ агента в общую историю прогона (её видят следующие агенты). Дефолт true.
  saveToHistory?: boolean;
  // Если ответ — JSON, в историю кладётся только это поле схемы, а не весь JSON.
  historyField?: string;

  [key: string]: unknown;
}

export interface Condition {
  name?: string;
  expression: string;
}

export interface ConditionNodeConfig extends Record<string, unknown> {
  conditions: Condition[];
}

export interface UpdateVariable extends Record<string, unknown> {
  variableName: string;
  value: string | number | boolean | Record<string, unknown> | unknown[];
}

export type MergeOperation = "add" | "subtract" | "overwrite";
export type MergeTarget = "state" | "project";

export interface SmartMerge extends Record<string, unknown> {
  source: string;
  target: MergeTarget;
  targetKey?: string; // specific key in state (e.g. "inventory"), empty = whole state
  operation: MergeOperation;
}

export interface SetVariableNodeConfig extends Record<string, unknown> {
  updates: UpdateVariable[];
  merges?: SmartMerge[];
}

export type OutputMode = "last_agent" | "specific_agent" | "custom";
export type FilterMode = "all" | "none" | "selected";

export interface EndNodeConfig extends Record<string, unknown> {
  name?: string;

  // Output Source
  outputMode?: OutputMode; // default: undefined = "last_agent"
  sourceNodeId?: string; // для specific_agent
  customMessage?: string; // для custom (поддержка CEL)

  // State Filtering
  stateFilter?: FilterMode; // default: "all"
  stateVariables?: string[];

  // Project Filtering
  projectFilter?: FilterMode; // default: "all"
  projectVariables?: string[];

  // Business Error
  isError?: boolean;
  errorMessage?: string; // поддержка CEL

  // Session
  isSessionEnd?: boolean;
}

export interface StickerNodeConfig extends Record<string, unknown> {
  text: string;
  width?: number;
  height?: number;
}

export interface HTTPRequestNodeConfig extends Record<string, unknown> {
  url: string;
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  headers?: Record<string, string>;
  body?: string;
  query_params?: Record<string, string>;
  timeout?: number;
}

// Базовый узел и конкретные реализации

export interface BaseNode {
  id: string;
  position: { x: number; y: number };
}

export interface StartNode extends BaseNode {
  type: NodeType.START;
  config: StartNodeConfig;
  nextNode: string;
}

export interface AgentNode extends BaseNode {
  type: NodeType.AGENT;
  config: AgentNodeConfig;
  nextNode: string;
}

export interface ConditionNode extends BaseNode {
  type: NodeType.CONDITION;
  config: ConditionNodeConfig;
}

export interface SetVariableNode extends BaseNode {
  type: NodeType.SET_VARIABLE;
  config: SetVariableNodeConfig;
  nextNode: string;
}

export interface EndNode extends BaseNode {
  type: NodeType.END;
  config: EndNodeConfig;
}

export interface StickerNode extends BaseNode {
  type: NodeType.STICKER;
  config: StickerNodeConfig;
}

export interface HTTPRequestNode extends BaseNode {
  type: NodeType.HTTP_REQUEST;
  config: HTTPRequestNodeConfig;
  nextNode: string;
}

export type Node =
  | StartNode
  | AgentNode
  | ConditionNode
  | SetVariableNode
  | EndNode
  | StickerNode
  | HTTPRequestNode;

export interface Edge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface StateVariable {
  name: string;
  defaultValue?: number | string | boolean | Record<string, unknown> | null;
  type: "number" | "string" | "boolean" | "object";
}

// Node Descriptor types (Phase 5 Node SDK)

export type NodePropertyType =
  | "string" | "text" | "number" | "boolean" | "options"
  | "json" | "code" | "credential" | "knowledge_base" | "key_value" | "collection";

export interface NodePropertyOption { value: string; label: string; }
export interface NodeDisplayCondition { field: string; values: unknown[]; }
export interface NodeProperty {
  name: string;
  displayName: string;
  type: NodePropertyType;
  default?: unknown;
  required?: boolean;
  placeholder?: string;
  description?: string;
  options?: NodePropertyOption[];
  showWhen?: NodeDisplayCondition | null;
  fields?: NodeProperty[];
}
export interface NodeDescriptor {
  type: string;
  displayName: string;
  description?: string;
  category: string;
  icon: string;
  color: string;
  sidebarVisible: boolean;
  isTerminal: boolean;
  branching: boolean;
  properties: NodeProperty[];
}
