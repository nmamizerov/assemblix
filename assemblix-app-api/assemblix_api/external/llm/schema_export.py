"""Builds the provider JSON schema for the frontend.

The frontend receives `paramSchema` and `models` over REST and decides which
fields to render for the chosen model — or requests an already-filtered schema
via `?model={id}`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from assemblix_api.dto.base import DTOModel
from assemblix_api.external.llm.base import (
    ModelMetadata,
    ParamCondition,
    ParamDef,
    ParamOption,
)

if TYPE_CHECKING:
    from assemblix_api.external.llm.model_catalog import ProviderDescriptor


class ProviderSchema(DTOModel):
    param_schema: list[ParamDef]
    models: list[ModelMetadata]


def _condition_matches(condition: ParamCondition | None, model: ModelMetadata) -> bool | None:
    """Match a single `ParamCondition` against a model.

    - None: condition not set (neither capability nor model_name).
    - True: model satisfies the condition.
    - False: model does NOT satisfy the condition.

    capability is OR (one match is enough); model_name requires the model to be
    in the list; if both are set, both must hold (AND).
    """
    if condition is None:
        return None
    capability = condition.capability
    model_name = condition.model_name
    if not capability and not model_name:
        return None

    if capability:
        cap_match = any(getattr(model.capabilities, c, False) for c in capability)
        if not cap_match:
            return False
    return not (model_name and model.id not in model_name)


def _is_visible(
    show: ParamCondition | None,
    hide: ParamCondition | None,
    model: ModelMetadata,
) -> bool:
    """Visibility logic: `show` must hold (if set), `hide` must not; `hide`
    wins over `show` on conflict."""
    show_result = _condition_matches(show, model)
    if show_result is False:
        return False
    hide_result = _condition_matches(hide, model)
    return hide_result is not True


def is_param_visible(param: ParamDef, model: ModelMetadata) -> bool:
    return _is_visible(param.show, param.hide, model)


def is_option_visible(option: ParamOption, model: ModelMetadata) -> bool:
    return _is_visible(option.show, option.hide, model)


def build_provider_schema(
    provider: ProviderDescriptor, model_id: str | None = None
) -> ProviderSchema:
    """Build the provider schema for the frontend.

    Without `model_id`: returns everything; the frontend filters itself using
    `paramSchema` and `models[].capabilities`. With `model_id`: pre-filters and
    returns only the visible params with filtered options.
    """
    if model_id is None:
        return ProviderSchema(
            param_schema=list(provider.param_schema),
            models=list(provider.models),
        )

    model = provider.find_model(model_id)
    if model is None:
        raise ValueError(f"Model {model_id!r} not found in provider {provider.name!r}")

    visible: list[ParamDef] = []
    for param in provider.param_schema:
        if not is_param_visible(param, model):
            continue
        if param.options:
            filtered_options = [opt for opt in param.options if is_option_visible(opt, model)]
            if filtered_options != list(param.options):
                visible.append(param.model_copy(update={"options": filtered_options}))
                continue
        visible.append(param)

    return ProviderSchema(param_schema=visible, models=[model])
