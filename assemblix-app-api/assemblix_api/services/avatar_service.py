"""Avatar session orchestration: build the persona from the workflow-global
avatar config, resolve the BYO key, and mint a provider session token."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.user import User
from assemblix_api.dto.responses.avatar import AvatarSessionResponse
from assemblix_api.external.avatar.session import mint_session
from assemblix_api.schemas.workflow import parse_avatar_config
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.workflow_service import WorkflowService

_CUSTOMER_LLM_ID = "CUSTOMER_CLIENT_V1"  # disables anam's brain; we push text


class AvatarService:
    def __init__(
        self,
        workflow_service: WorkflowService,
        credentials_service: CredentialsService,
        project_service: ProjectService,
    ) -> None:
        self._workflows = workflow_service
        self._credentials = credentials_service
        self._projects = project_service

    async def mint_workflow_session(
        self,
        workflow_id: UUID,
        user: User,
        scoped_project_id: UUID | None = None,
    ) -> AvatarSessionResponse:
        workflow = await self._workflows.get_by_id(workflow_id)
        await self._projects.verify_user_project_access(user, workflow.project_id)
        if scoped_project_id is not None and scoped_project_id != workflow.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API-ключ не имеет доступа к этому проекту",
            )

        avatar = parse_avatar_config(workflow.config or {})
        if avatar is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This workflow has no avatar configured",
            )

        # anam rejects an under-defined persona (it mints a now-unsupported legacy
        # token), so a real avatar and voice must both be selected.
        if not avatar.avatar_id or not avatar.voice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select both an avatar and a voice for this workflow's avatar",
            )

        api_key = await self._credentials.get_avatar_api_key_with_fallback(
            credentials_id=UUID(avatar.credential_id) if avatar.credential_id else None,
            project_id=workflow.project_id,
            avatar_provider=avatar.provider,
        )

        persona_config = {
            "name": "Assemblix",
            "avatarId": avatar.avatar_id,
            "avatarModel": avatar.avatar_model,
            "voiceId": avatar.voice_id,
            "llmId": _CUSTOMER_LLM_ID,
        }
        persona_config = {k: v for k, v in persona_config.items() if v is not None}

        session_token = await mint_session(
            provider=avatar.provider, api_key=api_key, persona_config=persona_config
        )
        return AvatarSessionResponse(
            provider=avatar.provider,
            session_token=session_token,
            video_config={"avatarModel": avatar.avatar_model},
        )
