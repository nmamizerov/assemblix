export enum ExecutionStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum StepStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum ExecutionErrorType {
  VALIDATION_ERROR = "validation_error",
  NODE_EXECUTION_ERROR = "node_execution_error",
  TIMEOUT_ERROR = "timeout_error",
  UNKNOWN_ERROR = "unknown_error",
}

export interface ExecutionStepResponse {
  id: string;
  executionId: string;
  stepNumber: number;
  nodeId: string;
  nodeType: string;
  inputData: Record<string, unknown>;
  outputData?: Record<string, unknown> | null;
  stateBefore: Record<string, unknown>;
  stateAfter?: Record<string, unknown> | null;
  status: StepStatus;
  errorMessage?: string | null;
  startedAt: string;
  completedAt?: string | null;
  durationMs: number;
  credits?: number | null;
  modelUsed?: string | null;
  celEvaluations?: Record<string, unknown> | null;
}

export interface ChatSessionBaseResponse {
  id: string;
  workflowId: string;
  userId: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface WorkflowResponse {
  id: string;
  name: string;
  description?: string | null;
  isActive: boolean;
  isPublished: boolean;
  createdAt: string;
  updatedAt: string;
  nodes?: unknown[];
  edges?: unknown[];
}

export interface ExecutionListItem {
  id: string;
  workflowId: string;
  status: ExecutionStatus;
  startedAt: string;
  completedAt?: string | null;
  durationMs: number;
  totalCredits: number;
  stepsCount: number;
  clientSessionId?: string | null;
  workflow: {
    id: string;
    name: string;
  };
}

export interface ExecutionDetailResponse
  extends Omit<ExecutionListItem, "workflow"> {
  userId: string;
  chatSessionId?: string | null;
  initialState: Record<string, unknown>;
  finalState?: Record<string, unknown> | null;
  isDebug: boolean;
  errorMessage?: string | null;
  errorType?: ExecutionErrorType | null;
  failedNodeId?: string | null;
  metaData: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  steps: ExecutionStepResponse[];
  workflow: WorkflowResponse;
  chatSession?: ChatSessionBaseResponse | null;
}
