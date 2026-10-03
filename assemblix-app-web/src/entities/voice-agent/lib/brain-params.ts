import {
  filterVisibleOptions,
  filterVisibleParams,
} from "@/entities/llm-provider";
import type { ModelMetadata, ParamDef } from "@/entities/llm-provider";

// A voice reply is spoken, never parsed — the brain has no use for JSON mode.
const HIDDEN_BRAIN_PARAMS = new Set(["response_format"]);

// The main voice-latency knobs stay visible instead of under "more settings".
const PROMINENT_BRAIN_PARAMS = new Set([
  "thinking_level",
  "thinking_budget",
  "reasoning_effort",
]);

const REPLY_TOKEN_CAP = 300;
// OpenAI counts reasoning tokens against this cap; too low a cap yields empty replies.
const REASONING_TOKEN_CAP = 1000;

export const brainParamSchema = (schema: ParamDef[]): ParamDef[] =>
  schema
    .filter((param) => !HIDDEN_BRAIN_PARAMS.has(param.name))
    .map((param) =>
      PROMINENT_BRAIN_PARAMS.has(param.name) ? { ...param, advanced: false } : param
    );

/**
 * Latency-friendly params for a voice brain: the least thinking the model
 * accepts and a short reply cap. Only params the schema shows for the model.
 */
export const voiceBrainDefaults = (
  schema: ParamDef[],
  model: ModelMetadata | undefined
): Record<string, unknown> => {
  if (!model) return {};
  const visible = new Map(
    filterVisibleParams(brainParamSchema(schema), model).map((param) => [
      param.name,
      param,
    ])
  );
  const params: Record<string, unknown> = {};

  const thinkingLevel = visible.get("thinking_level");
  if (thinkingLevel) {
    const [lowest] = filterVisibleOptions(thinkingLevel.options, model);
    if (lowest) params.thinking_level = lowest.value;
  }

  const thinkingBudget = visible.get("thinking_budget");
  // Gemini 2.5 Pro cannot turn thinking off; only Flash models accept 0.
  if (
    thinkingBudget &&
    model.id.includes("flash") &&
    (thinkingBudget.min ?? 0) <= 0
  ) {
    params.thinking_budget = 0;
  }

  const reasoningEffort = visible.get("reasoning_effort");
  if (reasoningEffort) {
    // "off" only omits the param, leaving the provider's own (higher) default.
    const [lowest] = filterVisibleOptions(reasoningEffort.options, model).filter(
      (option) => option.value !== "off"
    );
    if (lowest) params.reasoning_effort = lowest.value;
  }

  if (visible.has("max_completion_tokens")) {
    params.max_completion_tokens = REASONING_TOKEN_CAP;
  } else if (visible.has("max_tokens")) {
    params.max_tokens = REPLY_TOKEN_CAP;
  }

  return params;
};
