"""Voice provider/model discovery endpoints.

Powers the START-node "accept voice" picker on the frontend: the UI fetches the
transcription providers and their models to render the same provider→model
selection the agent node uses. Read-only, returns data straight from the voice
model catalog; requires an authenticated user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assemblix_api.database.models.user import User
from assemblix_api.dependencies import get_current_user
from assemblix_api.dto.responses.voice import VoiceProviderListItem
from assemblix_api.external.voice.base import VoiceModelMetadata
from assemblix_api.external.voice.voice_catalog import (
    VOICE_PROVIDER_LABELS,
    list_voice_models,
    list_voice_providers,
)

router = APIRouter(prefix="/voice", tags=["Voice"])

_CAPABILITY = "transcription"


@router.get("/providers", response_model=list[VoiceProviderListItem])
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> list[VoiceProviderListItem]:
    """List voice providers that expose transcription models."""
    return [
        VoiceProviderListItem(
            name=name,
            label=VOICE_PROVIDER_LABELS[name],
            models_count=len(list_voice_models(name, _CAPABILITY)),
        )
        for name in list_voice_providers(_CAPABILITY)
    ]


@router.get("/providers/{provider_name}/models", response_model=list[VoiceModelMetadata])
async def list_provider_models(
    provider_name: str,
    capability: str = Query(default=_CAPABILITY, description="Model capability filter"),
    current_user: User = Depends(get_current_user),
) -> list[VoiceModelMetadata]:
    """List a provider's voice models filtered by capability (default transcription)."""
    if provider_name not in VOICE_PROVIDER_LABELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice provider {provider_name!r} is not registered",
        )
    return list_voice_models(provider_name, capability)
