"""
Contracts of the LLM provider layer.

All REST-visible types (`ModelMetadata`, `ModelCapabilities`, `ParamDef`,
`ParamCondition`, `ParamOption`) inherit from `DTOModel` and are serialized
in camelCase. `TokenUsage` (a plain pydantic.BaseModel) is used for token
accounting during cost calculation and is not exposed via the API directly.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from assemblix_api.dto.base import DTOModel

# ---------------------------------------------------------------------------
# REST-visible models (camelCase on the wire)
# ---------------------------------------------------------------------------


class ModelCapabilities(DTOModel):
    """Filter flags consumed by parameter visibility rules.

    These flags exist solely so `paramSchema` entries can use
    `show.capability` / `hide.capability` to switch fields per model.
    UI hints (vision, tool-calling, etc.) live in the model's marketing
    description, not here.
    """

    reasoning: bool = Field(
        default=False,
        description=(
            "Whether the model is a reasoning-only model where "
            "`temperature` / `top_p` are rejected and `reasoning_effort` "
            "(or model-specific equivalent) is the canonical control "
            "(OpenAI o-series and GPT-5 reasoning family, DeepSeek R1)."
        ),
    )
    thinking: bool = Field(
        default=False,
        description=(
            "Whether the model supports opt-in extended thinking with an "
            "integer `thinking_budget` parameter (Anthropic Claude 4 "
            "extended thinking, Gemini 2.5 hybrid thinking)."
        ),
    )
    gen3: bool = Field(
        default=False,
        description=(
            "Whether the model is in the Gemini 3+ family that uses the "
            "`thinking_level` enum (minimal/low/medium/high) instead of "
            "an integer `thinking_budget`. Named `gen3` (no underscore) so "
            "the alias_generator passes it through as-is — keeping the "
            "snake_case key consistent with the camelCase serialization "
            "front-end clients see."
        ),
    )
    reasoning_effort_minimal: bool = Field(
        default=False,
        description=(
            "Whether the model accepts `reasoning_effort='minimal'`. "
            "True for the OpenAI gpt-5 family before 5.1 (gpt-5, "
            "gpt-5-mini, gpt-5-nano); gpt-5.1+ rejects it in favour of "
            "`none`."
        ),
    )
    reasoning_effort_xhigh: bool = Field(
        default=False,
        description=(
            "Whether the model accepts `reasoning_effort='xhigh'`. "
            "True for top-tier OpenAI reasoning models (gpt-5.2, "
            "gpt-5.4 family, gpt-5.5); rejected by gpt-5.1 and earlier."
        ),
    )
    accepts_audio: bool = Field(
        default=False,
        description="Model accepts audio input parts natively (skip STT).",
    )


class ModelMetadata(DTOModel):
    """Static metadata for a single LLM model exposed by a provider."""

    id: str = Field(
        description=(
            "Provider-specific model identifier used in API calls "
            "(e.g., 'gpt-4o', 'claude-opus-4-7')."
        ),
    )
    label: str = Field(
        description="Human-readable model name shown in the UI.",
    )
    description: str | None = Field(
        default=None,
        description="Short marketing/usage description shown to users.",
    )
    context_window: int = Field(
        description="Maximum number of input tokens the model accepts.",
    )
    max_output_tokens: int = Field(
        description="Maximum number of output tokens the model can generate.",
    )
    input_cost_per_million: float = Field(
        description="Cost in USD per 1,000,000 input tokens.",
    )
    output_cost_per_million: float = Field(
        description="Cost in USD per 1,000,000 output tokens.",
    )
    capabilities: ModelCapabilities = Field(
        description="Feature flags driving parameter visibility and UI hints.",
    )


class ParamCondition(DTOModel):
    """Condition controlling whether a `ParamDef` or `ParamOption` is
    visible for a given model."""

    capability: list[str] | None = Field(
        default=None,
        description=(
            "Capability flags from `ModelCapabilities` that satisfy the "
            "condition (OR semantics). Preferred over `model_name` because "
            "it scales when new models are added."
        ),
    )
    model_name: list[str] | None = Field(
        default=None,
        description=(
            "Explicit list of model IDs that satisfy the condition. "
            "Escape hatch for cases where capability flags are insufficient."
        ),
    )


class ParamOption(DTOModel):
    """Single choice in a `select`-type parameter."""

    label: str = Field(
        description="Human-readable option label shown in the UI.",
    )
    value: str | int | float | bool = Field(
        description=("Underlying value sent to the provider when this option is selected."),
    )
    show: ParamCondition | None = Field(
        default=None,
        description=(
            "Visibility condition. The option is shown only when this "
            "condition is satisfied for the selected model. Used to hide "
            "model-specific values like `reasoning_effort='xhigh'` "
            "(only some gpt-5.2+ models) or `'minimal'` (only pre-5.1 "
            "gpt-5 models)."
        ),
    )
    hide: ParamCondition | None = Field(
        default=None,
        description=(
            "Inverse visibility condition. The option is hidden when "
            "satisfied; `hide` takes precedence over `show`."
        ),
    )


class ParamDef(DTOModel):
    """Declarative schema entry for a single tunable parameter."""

    name: str = Field(
        description=(
            "Parameter key sent to the provider (e.g., 'temperature', 'reasoning_effort')."
        ),
    )
    label: str = Field(
        description="Human-readable parameter label shown in the UI.",
    )
    type: Literal["number", "string", "boolean", "select", "json"] = Field(
        description="Form control type used by the frontend renderer.",
    )
    default: Any = Field(
        default=None,
        description=("Default value applied when the user does not override the parameter."),
    )
    min: float | None = Field(
        default=None,
        description="Minimum numeric value (used by `number`-type fields).",
    )
    max: float | None = Field(
        default=None,
        description="Maximum numeric value (used by `number`-type fields).",
    )
    options: list[ParamOption] | None = Field(
        default=None,
        description="Available choices for `select`-type parameters.",
    )
    show: ParamCondition | None = Field(
        default=None,
        description=(
            "Visibility condition. The parameter is shown only when this "
            "condition is satisfied for the selected model."
        ),
    )
    hide: ParamCondition | None = Field(
        default=None,
        description=(
            "Inverse visibility condition. The parameter is hidden when "
            "satisfied; `hide` takes precedence over `show`."
        ),
    )
    advanced: bool = Field(
        default=False,
        description=(
            "Whether the parameter belongs to the 'advanced' section of the "
            "form (collapsed by default)."
        ),
    )
    description: str | None = Field(
        default=None,
        description="Tooltip/help text shown next to the parameter in the UI.",
    )


# ---------------------------------------------------------------------------
# Token accounting (used during cost calculation)
# ---------------------------------------------------------------------------


class TokenUsage(BaseModel):
    """Token accounting reported by the provider for a single completion."""

    input_tokens: int = Field(
        default=0,
        description="Number of tokens in the prompt sent to the model.",
    )
    output_tokens: int = Field(
        default=0,
        description="Number of tokens generated by the model.",
    )
    total_tokens: int = Field(
        default=0,
        description="Sum of input and output tokens reported by the provider.",
    )
