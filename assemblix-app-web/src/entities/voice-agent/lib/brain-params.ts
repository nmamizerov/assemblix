import {
  filterVisibleOptions,
  filterVisibleParams,
} from "@/entities/llm-provider";
import type { ModelMetadata, ParamDef } from "@/entities/llm-provider";

// A voice reply is spoken, never parsed — the brain has no use for JSON mode.
const HIDDEN_BRAIN_PARAMS = new Set(["response_format"]);

const REPLY_TOKEN_CAP = 300;

export const brainParamSchema = (schema: ParamDef[]): ParamDef[] =>
  schema.filter((param) => !HIDDEN_BRAIN_PARAMS.has(param.name));

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

  const tokenCap = ["max_completion_tokens", "max_tokens"].find((name) =>
    visible.has(name)
  );
  if (tokenCap) params[tokenCap] = REPLY_TOKEN_CAP;

  return params;
};
