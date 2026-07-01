# /external/llm/model_catalog.py
"""Catalog of model metadata from `models/<provider>.json`.

ModelMetadata used to be obtained through provider objects (`ProviderRegistry`).
After moving to Pydantic AI there are no provider objects, but the JSON model
registry remains (it also feeds the UI schema and cost calculation). This module
reads it directly — the single source of prices/context/capabilities per (provider, model).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from assemblix_api.external.llm.base import ModelMetadata, ParamDef
from assemblix_api.external.llm.models_loader import load_provider_data

# Registered providers: key → human-readable label.
# The label used to live in provider bootstraps (OpenAI/DeepSeek/...). Anthropic is
# not included (it was commented out in the old registry).
PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "gemini": "Google Gemini",
}


@cache
def _models_for(provider: str) -> dict[str, ModelMetadata]:
    try:
        data = load_provider_data(f"{provider}.json")
    except (FileNotFoundError, OSError):
        return {}
    return {m.id: m for m in data.models}


def find_model_metadata(provider: str, model: str) -> ModelMetadata | None:
    """Model metadata by (provider, model), or None if not found."""
    return _models_for(provider).get(model)


@dataclass(frozen=True)
class ProviderDescriptor:
    """Lightweight provider description for the UI schema (replaces heavy provider objects).

    Contains exactly what the /llm endpoints and `build_provider_schema` need:
    name, label, models and the parameter schema — all from `models/<provider>.json`.
    """

    name: str
    label: str
    models: list[ModelMetadata]
    param_schema: list[ParamDef]

    def find_model(self, model_id: str) -> ModelMetadata | None:
        return next((m for m in self.models if m.id == model_id), None)


@cache
def get_provider_descriptor(name: str) -> ProviderDescriptor | None:
    """Descriptor of a registered provider, or None if not registered."""
    label = PROVIDER_LABELS.get(name)
    if label is None:
        return None
    data = load_provider_data(f"{name}.json")
    return ProviderDescriptor(
        name=name,
        label=label,
        models=list(data.models),
        param_schema=list(data.param_schema),
    )


def list_provider_descriptors() -> list[ProviderDescriptor]:
    """All registered providers (for the list endpoint)."""
    return [d for n in PROVIDER_LABELS if (d := get_provider_descriptor(n)) is not None]
