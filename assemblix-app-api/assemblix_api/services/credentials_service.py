"""
Credentials service - business logic for credentials
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.billing.plans import get_plan_config
from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.credentials import Credentials, CredentialsType
from assemblix_api.database.repositories.credentials_repository import (
    CredentialsRepository,
)
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.enums import AgentProvider, PlanTier
from assemblix_api.services.base_service import BaseService

if TYPE_CHECKING:
    from assemblix_api.dto.requests.credentials import (
        CredentialsCreateRequest,
        CredentialsUpdateRequest,
    )


class CredentialsService(BaseService[Credentials, CredentialsRepository]):
    def __init__(
        self,
        repository: CredentialsRepository,
        org_user_repository: OrganizationUserRepository,
    ):
        super().__init__(repository, entity_name="Credentials")
        self._org_user_repository = org_user_repository

    async def create_credentials(
        self,
        *,
        project_id: UUID,
        data: CredentialsCreateRequest,
    ) -> Credentials:
        credentials_data = data.model_dump()
        credentials_data["project_id"] = project_id

        return await self.create(**credentials_data)

    async def update_credentials(
        self,
        credentials_id: UUID,
        project_id: UUID,
        *,
        data: CredentialsUpdateRequest,
    ) -> Credentials:
        await self._check_ownership(credentials_id, project_id)

        # Only explicitly-set fields; service fields are never updatable
        update_data = data.model_dump(
            exclude_unset=True,
            exclude={"id", "project_id", "type", "created_at", "updated_at"},
        )

        return await self.update(credentials_id, **update_data)

    async def delete_credentials(self, credentials_id: UUID, project_id: UUID) -> None:
        await self._check_ownership(credentials_id, project_id)
        await self.delete(credentials_id)

    async def get_project_credentials(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        type: CredentialsType | None = None,
    ) -> Sequence[Credentials]:
        return await self._repository.get_by_project_id(
            project_id,
            skip=skip,
            limit=limit,
            type=type,
        )

    async def get_decrypted_api_key(self, credentials_id: UUID, project_id: UUID) -> str:
        """
        Return the decrypted API key for backend-internal use only.

        WARNING: backend-only (e.g. LLM provider calls from the workflow engine).
        NEVER return the result of this method to the frontend.
        """
        await self._check_ownership(credentials_id, project_id)

        return await self._repository.get_decrypted_value(credentials_id)

    async def get_api_key_with_fallback(
        self,
        credentials_id: UUID | None,
        project_id: UUID,
        provider: AgentProvider,
        organization_plan: PlanTier,
    ) -> tuple[str, bool]:
        """
        Resolve the API key, falling back to a system key.

        Key selection:
        - Plans without can_use_own_keys (e.g. FREE): always the system key.
        - Plans with own keys: use the supplied credential if present and valid,
          otherwise fall back to the system key.

        Returns (api_key, is_system_key).
        """
        settings = get_settings()
        plan_config = get_plan_config(organization_plan)

        if not plan_config.can_use_own_keys:
            return self._get_system_key(provider, settings), True

        if credentials_id:
            try:
                credentials = await self._check_ownership(credentials_id, project_id)

                if not self._is_provider_compatible(provider, credentials.type):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Credentials type {credentials.type.value} is not compatible with provider {provider.value}",
                    )

                api_key = await self.get_decrypted_api_key(credentials_id, project_id)
                return api_key, False

            except HTTPException:
                # Missing credential or no access -> fall back to the system key
                pass

        return self._get_system_key(provider, settings), True

    _VOICE_PROVIDER_TO_CREDENTIALS_TYPE = {
        "openai": CredentialsType.OPENAI_TOKEN,
        "elevenlabs": CredentialsType.ELEVENLABS_TOKEN,
        "yandex": CredentialsType.YANDEX_SPEECHKIT_TOKEN,
    }

    async def get_voice_api_key_with_fallback(
        self,
        credentials_id: UUID | None,
        project_id: UUID,
        voice_provider: str,
        organization_plan: PlanTier,
    ) -> tuple[str, bool]:
        """Resolve a voice-provider API key, falling back to the system key.

        Mirrors get_api_key_with_fallback but for voice providers (not AgentProvider):
        FREE always uses the system key; paid plans use a valid own credential else
        fall back. Returns (api_key, is_system_key). Raises 503 when no key exists.
        """
        settings = get_settings()
        plan_config = get_plan_config(organization_plan)

        if not plan_config.can_use_own_keys:
            return self._get_voice_system_key(voice_provider, settings), True

        if credentials_id:
            try:
                credentials = await self._check_ownership(credentials_id, project_id)
                expected = self._VOICE_PROVIDER_TO_CREDENTIALS_TYPE.get(voice_provider)
                if expected is None or credentials.type != expected:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Credentials type is not compatible with voice provider {voice_provider}",
                    )
                api_key = await self.get_decrypted_api_key(credentials_id, project_id)
                return api_key, False
            except HTTPException:
                # Missing / not-owned / incompatible -> fall back to the system key.
                pass

        return self._get_voice_system_key(voice_provider, settings), True

    _AVATAR_PROVIDER_TO_CREDENTIALS_TYPE = {"anam": CredentialsType.ANAM_TOKEN}

    async def get_avatar_api_key_with_fallback(
        self,
        credentials_id: UUID | None,
        project_id: UUID,
        avatar_provider: str,
    ) -> str:
        """Resolve an avatar-provider API key. BYO-only: no system key.

        A missing, unowned, or incompatible credential is a hard 400 (unlike the
        voice resolver, avatars have no system-key fallback this phase).
        """
        expected = self._AVATAR_PROVIDER_TO_CREDENTIALS_TYPE.get(avatar_provider)
        if expected is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown avatar provider {avatar_provider!r}",
            )
        if not credentials_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An avatar provider credential is required for {avatar_provider}",
            )
        credentials = await self._check_ownership(credentials_id, project_id)
        if credentials.type != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credentials type is not compatible with avatar provider {avatar_provider}",
            )
        return await self.get_decrypted_api_key(credentials_id, project_id)

    def _get_voice_system_key(self, voice_provider: str, settings) -> str:
        """Return the configured system key for a voice provider, or raise 503.

        Yandex needs two secrets, so its system value is packed as
        ``"<folderId>:<apiKey>"`` — the same shape stored in a BYO credential.
        """
        if voice_provider == "yandex":
            key = settings.system_yandex_speechkit_api_key
            folder = settings.system_yandex_speechkit_folder_id
            api_key = f"{folder}:{key}" if key and folder else ""
        else:
            key_map = {
                "openai": settings.system_openai_api_key,
                "elevenlabs": settings.system_elevenlabs_api_key,
            }
            api_key = key_map.get(voice_provider, "")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"System API key for voice provider {voice_provider} is not configured.",
            )
        return api_key

    def _get_system_key(self, provider: AgentProvider, settings) -> str:
        """Return the configured system API key for the provider, or raise 503."""
        key_map = {
            AgentProvider.OPENAI: settings.system_openai_api_key,
            AgentProvider.GEMINI: settings.system_gemini_api_key,
            AgentProvider.DEEPSEEK: settings.system_deepseek_api_key,
        }

        api_key = key_map.get(provider, "")

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"System API key for {provider.value} is not configured. Please contact support.",
            )

        return api_key

    def _is_provider_compatible(
        self, provider: AgentProvider, credentials_type: CredentialsType
    ) -> bool:
        compatibility_map = {
            AgentProvider.OPENAI: CredentialsType.OPENAI_TOKEN,
            AgentProvider.GEMINI: CredentialsType.GEMINI_TOKEN,
            AgentProvider.DEEPSEEK: CredentialsType.DEEPSEEK_TOKEN,
        }

        return compatibility_map.get(provider) == credentials_type

    def _credentials_type_to_provider(self, credentials_type: CredentialsType) -> AgentProvider:
        type_to_provider = {
            CredentialsType.OPENAI_TOKEN: AgentProvider.OPENAI,
            CredentialsType.GEMINI_TOKEN: AgentProvider.GEMINI,
            CredentialsType.DEEPSEEK_TOKEN: AgentProvider.DEEPSEEK,
        }

        provider = type_to_provider.get(credentials_type)
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый тип провайдера: {credentials_type.value}",
            )

        return provider

    def _agent_provider_to_credentials_type(self, provider: AgentProvider) -> CredentialsType:
        provider_to_type = {
            AgentProvider.OPENAI: CredentialsType.OPENAI_TOKEN,
            AgentProvider.GEMINI: CredentialsType.GEMINI_TOKEN,
            AgentProvider.DEEPSEEK: CredentialsType.DEEPSEEK_TOKEN,
        }

        credentials_type = provider_to_type.get(provider)
        if credentials_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый провайдер: {provider.value}",
            )

        return credentials_type

    async def _check_ownership(self, credentials_id: UUID, project_id: UUID) -> Credentials:
        """Return the credentials, raising 404/403 if missing or not in the project."""
        credentials = await self._repository.get_by_id(credentials_id)

        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credentials не найден",
            )

        if credentials.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для работы с этим credentials",
            )

        return credentials
