"""
API Keys REST endpoints
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.dependencies import (
    get_api_key_service,
    get_auth_context,
    get_project_id_from_token,
    get_project_service,
)
from assemblix_api.dto.requests.api_key import CreateAPIKeyRequest
from assemblix_api.dto.responses.api_key import (
    APIKeyCreatedResponse,
    APIKeyListResponse,
    APIKeyResponse,
)
from assemblix_api.services.api_key_service import APIKeyService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get("/whoami")
async def whoami(
    project_id: UUID = Depends(get_project_id_from_token),
) -> dict[str, str]:
    """Return the project the calling API key is scoped to."""
    return {"projectId": str(project_id)}


@router.get("/", response_model=APIKeyListResponse)
async def list_api_keys(
    project_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[APIKeyService, Depends(get_api_key_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
):
    """
    List the project's API keys.

    Plaintext keys are never returned - only metadata (name, prefix, usage stats,
    created/last-used dates).
    """
    await project_service.authorize_project_access(auth, project_id)
    keys = await service.list_project_keys(project_id)

    return APIKeyListResponse(
        keys=[APIKeyResponse.model_validate(key) for key in keys],
        total=len(keys),
    )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[APIKeyService, Depends(get_api_key_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
):
    """
    Get detailed information about an API key.

    Returns key metadata including usage stats. The plaintext key is never returned.
    """
    # Fetch the API key to resolve its project_id
    api_key_obj = await service._api_keys.get_by_id(key_id)
    if not api_key_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await project_service.authorize_project_access(auth, api_key_obj.project_id)
    api_key = await service.get_key_details(key_id, api_key_obj.project_id)
    return APIKeyResponse.model_validate(api_key)


@router.post("/", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: CreateAPIKeyRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[APIKeyService, Depends(get_api_key_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
):
    """
    Create a new API key for the project.

    IMPORTANT: the plaintext API key is returned ONLY ONCE. The key is hashed
    before being stored, so it cannot be retrieved again - the user must copy and
    save it now. If lost, a new key must be created.

    Key format: `sk_<32 hex chars>`, e.g. `sk_a1b2c3d4e5f67890123456789abcdef0`.

    Usage:
    ```
    curl -H "Authorization: Bearer sk_a1b2c3d4e5f67890123456789abcdef0" \\
         https://api.example.com/workflows
    ```
    """
    await project_service.authorize_project_access(auth, data.project_id)
    api_key, plain_key = await service.create_api_key(
        project_id=data.project_id,
        name=data.name,
    )

    return APIKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        api_key=plain_key,  # Returned only here!
        prefix=api_key.prefix,
        created_at=api_key.created_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[APIKeyService, Depends(get_api_key_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
):
    """
    Delete an API key.

    Permanently deletes the key; after deletion it can no longer be used for
    authentication. Verifies the key belongs to the user's project.
    """
    # Fetch the API key to resolve its project_id
    api_key = await service._api_keys.get_by_id(key_id)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await project_service.authorize_project_access(auth, api_key.project_id)
    await service.delete_api_key(key_id, api_key.project_id)
