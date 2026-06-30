"""Response DTOs for the `/api/llm` provider/model/schema endpoints."""

from __future__ import annotations

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class ProviderListItem(DTOModel):
    """Compact provider summary for the `/api/llm/providers` list endpoint."""

    name: str = Field(
        description=(
            "Stable provider identifier used everywhere as a key "
            "(e.g., 'openai', 'gemini', 'anthropic')."
        ),
    )
    label: str = Field(
        description="Human-readable provider name suitable for display.",
    )
    models_count: int = Field(
        description="Number of models the provider currently exposes.",
    )
