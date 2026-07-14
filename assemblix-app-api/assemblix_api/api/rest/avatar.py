"""Avatar provider/model discovery + workflow session-token minting.

Mirror of api/rest/voice.py. Discovery powers the editor-header avatar picker;
the session route hands the browser SDK a short-lived token (key never exposed).
Avatars are BYO-key only — there is no system-avatars endpoint.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_auth_context,
    get_avatar_service,
    get_credentials_service,
    get_current_user,
    get_project_service,
)
from assemblix_api.dto.responses.avatar import (
    AvatarListItem,
    AvatarProviderListItem,
    AvatarSessionResponse,
)
from assemblix_api.external.avatar.anam import list_avatars, list_voices
from assemblix_api.external.avatar.avatar_catalog import (
    AVATAR_PROVIDER_LABELS,
    list_avatar_models,
    list_avatar_providers,
)
from assemblix_api.external.avatar.base import AvatarModelMetadata
from assemblix_api.services.avatar_service import AvatarService
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(tags=["Avatar"])


@router.get("/avatar/providers", response_model=list[AvatarProviderListItem])
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> list[AvatarProviderListItem]:
    """List registered avatar providers with their model counts."""
    return [
        AvatarProviderListItem(
            name=name,
            label=AVATAR_PROVIDER_LABELS[name],
            models_count=len(list_avatar_models(name)),
        )
        for name in list_avatar_providers()
    ]


@router.get("/avatar/providers/{provider_name}/models", response_model=list[AvatarModelMetadata])
async def list_provider_models(
    provider_name: str,
    current_user: User = Depends(get_current_user),
) -> list[AvatarModelMetadata]:
    """List an avatar provider's models."""
    if provider_name not in AVATAR_PROVIDER_LABELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Avatar provider {provider_name!r} is not registered",
        )
    return list_avatar_models(provider_name)


@router.get("/avatar/credentials/{credentials_id}/avatars", response_model=list[AvatarListItem])
async def list_credential_avatars(
    credentials_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    credentials_service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
) -> list[AvatarListItem]:
    """List the anam avatars available to a stored credential."""
    credentials = await credentials_service.get_by_id(credentials_id)
    await project_service.authorize_project_access(auth, credentials.project_id)
    if credentials.type != CredentialsType.ANAM_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This credential is not an anam token",
        )
    api_key = await credentials_service.get_decrypted_api_key(
        credentials_id, credentials.project_id
    )
    avatars = await list_avatars(api_key)
    return [AvatarListItem(id=a.id, name=a.name) for a in avatars]


@router.get("/avatar/credentials/{credentials_id}/voices", response_model=list[AvatarListItem])
async def list_credential_voices(
    credentials_id: UUID,
    search: str | None = Query(default=None, description="Filter voices by display name"),
    auth: AuthContext = Depends(get_auth_context),
    credentials_service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
) -> list[AvatarListItem]:
    """List the anam voices available to a stored credential (optional name search)."""
    credentials = await credentials_service.get_by_id(credentials_id)
    await project_service.authorize_project_access(auth, credentials.project_id)
    if credentials.type != CredentialsType.ANAM_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This credential is not an anam token",
        )
    api_key = await credentials_service.get_decrypted_api_key(
        credentials_id, credentials.project_id
    )
    voices = await list_voices(api_key, search=search)
    return [AvatarListItem(id=v.id, name=v.name) for v in voices]


@router.post("/workflows/{workflow_id}/avatar/session", response_model=AvatarSessionResponse)
async def mint_avatar_session(
    workflow_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    avatar_service: AvatarService = Depends(get_avatar_service),
) -> AvatarSessionResponse:
    """Mint a client session token for the workflow's configured avatar persona."""
    return await avatar_service.mint_workflow_session(
        workflow_id, auth.user, scoped_project_id=auth.scoped_project_id
    )
