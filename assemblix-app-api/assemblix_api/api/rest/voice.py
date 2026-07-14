"""Voice provider/model discovery endpoints.

Powers voice-model pickers on the frontend (e.g. the START-node "accept voice"
picker and the END-node speech-output picker): the UI fetches providers and
their models for a given ``capability`` to render a provider→model selection.
All endpoints require an authenticated user. ``list_providers`` and
``list_provider_models`` return data straight from the in-memory voice model
catalog, but ``list_credential_voices`` makes a live authenticated call to the
ElevenLabs API using a decrypted stored credential.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_auth_context,
    get_credentials_service,
    get_current_user,
    get_project_service,
)
from assemblix_api.dto.responses.voice import VoiceListItem, VoiceProviderListItem
from assemblix_api.external.voice import yandex
from assemblix_api.external.voice.base import VoiceModelMetadata
from assemblix_api.external.voice.elevenlabs import list_voices
from assemblix_api.external.voice.voice_catalog import (
    VOICE_PROVIDER_LABELS,
    list_voice_models,
    list_voice_providers,
)
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/voice", tags=["Voice"])

_CAPABILITY = "transcription"


@router.get("/providers", response_model=list[VoiceProviderListItem])
async def list_providers(
    capability: str = Query(default=_CAPABILITY, description="Model capability filter"),
    current_user: User = Depends(get_current_user),
) -> list[VoiceProviderListItem]:
    """List voice providers exposing models for the given capability."""
    return [
        VoiceProviderListItem(
            name=name,
            label=VOICE_PROVIDER_LABELS[name],
            models_count=len(list_voice_models(name, capability)),
        )
        for name in list_voice_providers(capability)
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


@router.get("/credentials/{credentials_id}/voices", response_model=list[VoiceListItem])
async def list_credential_voices(
    credentials_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    credentials_service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
) -> list[VoiceListItem]:
    """List the voices available to a stored voice credential.

    ElevenLabs voices are fetched live per key; Yandex SpeechKit has a fixed
    catalog and needs no API call.
    """
    credentials = await credentials_service.get_by_id(credentials_id)
    await project_service.authorize_project_access(auth, credentials.project_id)

    if credentials.type == CredentialsType.YANDEX_SPEECHKIT_TOKEN:
        return [
            VoiceListItem(id=v.id, name=v.name, preview_url=v.preview_url)
            for v in yandex.list_voices()
        ]
    if credentials.type != CredentialsType.ELEVENLABS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This credential is not a voice-provider token",
        )
    api_key = await credentials_service.get_decrypted_api_key(
        credentials_id, credentials.project_id
    )
    voices = await list_voices(api_key)
    return [VoiceListItem(id=v.id, name=v.name, preview_url=v.preview_url) for v in voices]


@router.get("/providers/{provider_name}/system-voices", response_model=list[VoiceListItem])
async def list_system_voices(
    provider_name: str,
    current_user: User = Depends(get_current_user),
) -> list[VoiceListItem]:
    """List the voices available to the platform's system key for a voice provider.

    Used by the END-node voice picker when a run uses the system key (no personal
    credential). Requires an authenticated user; never exposes the key.
    """
    if provider_name == "yandex":
        # Fixed catalog; independent of whether a system key is configured.
        return [
            VoiceListItem(id=v.id, name=v.name, preview_url=v.preview_url)
            for v in yandex.list_voices()
        ]
    if provider_name != "elevenlabs":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No system voices for provider {provider_name!r}",
        )
    api_key = get_settings().system_elevenlabs_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System voice key is not configured",
        )
    voices = await list_voices(api_key)
    return [VoiceListItem(id=v.id, name=v.name, preview_url=v.preview_url) for v in voices]
