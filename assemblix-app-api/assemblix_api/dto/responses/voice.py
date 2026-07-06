"""Response DTOs for the `/api/voice` provider/model discovery endpoints."""

from __future__ import annotations

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class VoiceProviderListItem(DTOModel):
    """Compact provider summary for the `/api/voice/providers` list endpoint."""

    name: str = Field(
        description="Stable provider identifier used as a key (e.g. 'openai').",
    )
    label: str = Field(description="Human-readable provider name for display.")
    models_count: int = Field(
        description="Number of transcription models the provider exposes.",
    )


class VoiceListItem(DTOModel):
    """A voice from a provider account, for the END-node voice picker."""

    id: str
    name: str
    preview_url: str | None = None
