/**
 * Types for the dynamic LLM provider/model schema served from the
 * backend at `/api/llm/providers/...`. The shape mirrors
 * `assemblix_api/external/llm/base.py` and
 * `assemblix_api/external/llm/schema_export.py` (camelCase via `DTOModel`).
 */

export interface ProviderListItem {
  /** Stable provider id (e.g. "openai", "gemini"). */
  name: string;
  /** Human-readable provider label. */
  label: string;
  /** Number of models exposed by the provider. */
  modelsCount: number;
}

export interface ModelCapabilities {
  vision: boolean;
  tools: boolean;
  jsonMode: boolean;
  streaming: boolean;
  reasoning: boolean;
  thinking: boolean;
  reasoningEffortMinimal: boolean;
  reasoningEffortXhigh: boolean;
}

export interface ModelMetadata {
  id: string;
  label: string;
  description?: string | null;
  contextWindow: number;
  maxOutputTokens: number;
  inputCostPerMillion: number;
  outputCostPerMillion: number;
  capabilities: ModelCapabilities;
}

export type ParamType = "number" | "string" | "boolean" | "select" | "json";

export interface ParamCondition {
  /**
   * Capability flags that satisfy the condition (OR semantics).
   * Preferred over `modelName` because it scales when new models drop.
   */
  capability?: string[] | null;
  /** Explicit list of model ids — escape hatch. */
  modelName?: string[] | null;
}

export interface ParamOption {
  label: string;
  value: string | number | boolean;
  show?: ParamCondition | null;
  hide?: ParamCondition | null;
}

export interface ParamDef {
  name: string;
  label: string;
  type: ParamType;
  default?: unknown;
  min?: number | null;
  max?: number | null;
  options?: ParamOption[] | null;
  show?: ParamCondition | null;
  hide?: ParamCondition | null;
  advanced: boolean;
  description?: string | null;
}

export interface ProviderSchema {
  paramSchema: ParamDef[];
  models: ModelMetadata[];
}
