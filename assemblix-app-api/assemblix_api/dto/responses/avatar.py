"""Response DTOs for the /api/avatar discovery + session endpoints."""

from __future__ import annotations

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class AvatarProviderListItem(DTOModel):
    """Compact provider summary for the `/api/avatar/providers` list endpoint."""

    name: str = Field(
        description="Stable provider id, e.g. 'anam'.",
    )
    label: str = Field(description="Human-readable provider name.")
    models_count: int = Field(
        description="Number of avatar models the provider exposes.",
    )


class AvatarListItem(DTOModel):
    """An avatar model from a provider, for the avatar picker."""

    id: str
    name: str


class AvatarSessionResponse(DTOModel):
    """Everything the client SDK needs to connect; the API key never appears here."""

    provider: str
    session_token: str
    # Provider-specific hints the client passes to createClient (e.g. avatarModel).
    video_config: dict
