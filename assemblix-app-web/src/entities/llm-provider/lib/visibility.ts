import type {
  ModelCapabilities,
  ModelMetadata,
  ParamCondition,
  ParamDef,
  ParamOption,
} from "../model/types";

/**
 * Mirror of the backend `is_param_visible` / `is_option_visible` from
 * `assemblix_api/external/llm/schema_export.py`.
 *
 * Lets the frontend keep one in-memory schema for the provider and toggle
 * fields locally as the user picks different models — without re-fetching
 * `/api/llm/providers/{name}/schema?model=...` on every change.
 */

const matchesCondition = (
  condition: ParamCondition | null | undefined,
  model: ModelMetadata,
): boolean | null => {
  if (!condition) return null;
  const hasCapability = (condition.capability ?? []).length > 0;
  const hasModelName = (condition.modelName ?? []).length > 0;
  if (!hasCapability && !hasModelName) return null;

  if (hasCapability) {
    const capMatch = (condition.capability ?? []).some((cap) =>
      Boolean(model.capabilities[cap as keyof ModelCapabilities]),
    );
    if (!capMatch) return false;
  }
  if (hasModelName) {
    if (!(condition.modelName ?? []).includes(model.id)) return false;
  }
  return true;
};

const isVisible = (
  show: ParamCondition | null | undefined,
  hide: ParamCondition | null | undefined,
  model: ModelMetadata | undefined,
): boolean => {
  if (!model) return true;
  const showResult = matchesCondition(show, model);
  if (showResult === false) return false;
  const hideResult = matchesCondition(hide, model);
  if (hideResult === true) return false;
  return true;
};

export const isParamVisible = (
  param: ParamDef,
  model: ModelMetadata | undefined,
): boolean => isVisible(param.show, param.hide, model);

export const isOptionVisible = (
  option: ParamOption,
  model: ModelMetadata | undefined,
): boolean => isVisible(option.show, option.hide, model);

/**
 * Convenience helper: filter a parameter schema down to fields that should
 * render for a specific model.
 */
export const filterVisibleParams = (
  paramSchema: ParamDef[],
  model: ModelMetadata | undefined,
): ParamDef[] => paramSchema.filter((p) => isParamVisible(p, model));

/**
 * Filter the options of a `select`-type parameter down to the ones the
 * picked model actually accepts (e.g. drop `xhigh` on gpt-5.1).
 */
export const filterVisibleOptions = (
  options: ParamOption[] | null | undefined,
  model: ModelMetadata | undefined,
): ParamOption[] =>
  (options ?? []).filter((opt) => isOptionVisible(opt, model));
