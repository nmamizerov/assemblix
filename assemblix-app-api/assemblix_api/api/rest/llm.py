"""
LLM provider/model discovery endpoints.

Powers the dynamic agent-node form on the frontend: the UI fetches the
provider's `paramSchema` and `models` and renders fields based on
`show`/`hide` conditions and per-model `capabilities`. The schema is
declarative, so adding a new model ⇒ editing one JSON file ⇒ form
updates with no extra UI code.

All endpoints are read-only and return data straight from the JSON model
catalog (`model_catalog`). They require an authenticated user — these are the
same building blocks the workflow editor uses, not public docs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assemblix_api.database.models.user import User
from assemblix_api.dependencies import get_current_user
from assemblix_api.dto.responses.llm import ProviderListItem
from assemblix_api.external.llm.base import ModelMetadata
from assemblix_api.external.llm.model_catalog import (
    ProviderDescriptor,
    get_provider_descriptor,
    list_provider_descriptors,
)
from assemblix_api.external.llm.schema_export import (
    ProviderSchema,
    build_provider_schema,
)

router = APIRouter(prefix="/llm", tags=["LLM"])


@router.get("/providers", response_model=list[ProviderListItem])
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> list[ProviderListItem]:
    """List all registered LLM providers with model counts."""
    return [
        ProviderListItem(
            name=p.name,
            label=p.label,
            models_count=len(p.models),
        )
        for p in list_provider_descriptors()
    ]


@router.get("/providers/{provider_name}/models", response_model=list[ModelMetadata])
async def list_provider_models(
    provider_name: str,
    current_user: User = Depends(get_current_user),
) -> list[ModelMetadata]:
    """List models for a specific provider with full metadata."""
    provider = _get_provider_or_404(provider_name)
    return list(provider.models)


@router.get("/providers/{provider_name}/schema", response_model=ProviderSchema)
async def get_provider_schema(
    provider_name: str,
    model: str | None = Query(
        default=None,
        description=(
            "Optional model id to pre-filter the parameter schema by "
            "`show`/`hide` rules. Without this query param the response "
            "contains the full schema and `models` array, leaving "
            "filtering to the frontend."
        ),
    ),
    current_user: User = Depends(get_current_user),
) -> ProviderSchema:
    """Return the provider's parameter schema and model list.

    With `?model=...` the schema is pre-filtered to fields that are
    visible for that specific model (capability- and model-name-aware).
    """
    provider = _get_provider_or_404(provider_name)
    try:
        return build_provider_schema(provider, model_id=model)
    except ValueError as exc:
        # `model` was provided but doesn't exist in the provider's registry.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _get_provider_or_404(name: str) -> ProviderDescriptor:
    descriptor = get_provider_descriptor(name)
    if descriptor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM provider {name!r} is not registered",
        )
    return descriptor
