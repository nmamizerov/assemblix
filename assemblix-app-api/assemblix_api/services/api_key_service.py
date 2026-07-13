"""API Key Service."""

from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import HTTPException, status
from pwdlib import PasswordHash

from assemblix_api.database.models.api_key import APIKey
from assemblix_api.database.models.user import User
from assemblix_api.database.repositories.api_key_repository import APIKeyRepository
from assemblix_api.database.repositories.organization_repository import (
    OrganizationRepository,
)
from assemblix_api.database.repositories.project_repository import ProjectRepository
from assemblix_api.database.repositories.user_repository import UserRepository

_password_hash = PasswordHash.recommended()


class APIKeyService:
    def __init__(
        self,
        api_key_repository: APIKeyRepository,
        user_repository: UserRepository,
        project_repository: ProjectRepository,
        organization_repository: OrganizationRepository,
    ):
        self._api_keys = api_key_repository
        self._users = user_repository
        self._projects = project_repository
        self._organizations = organization_repository

    @staticmethod
    def generate_api_key() -> str:
        """Generate a random API key in the format sk_<32 hex chars>."""
        random_bytes = secrets.token_bytes(16)
        hex_string = random_bytes.hex()
        return f"sk_{hex_string}"

    @staticmethod
    def get_key_prefix(api_key: str) -> str:
        """Extract a display prefix ("sk_xxxxx...", first 11 chars) from an API key."""
        if len(api_key) < 11:
            return api_key
        return api_key[:11] + "..."

    async def create_api_key(
        self,
        project_id: UUID,
        name: str,
    ) -> tuple[APIKey, str]:
        """
        Create a new API key for a project.

        Returns (APIKey, plain_key); the plain-text key is exposed only here, once.
        """
        plain_key = self.generate_api_key()
        key_hash = _password_hash.hash(plain_key)
        prefix = self.get_key_prefix(plain_key)

        api_key = await self._api_keys.create(
            project_id=project_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
        )

        return api_key, plain_key

    async def resolve_context(self, plain_key: str) -> tuple[User, APIKey] | None:
        """Resolve a plain key to ``(owner_user, api_key)``.

        Resolves key -> project -> organization -> owner. Increments usage as a
        side effect. Returns ``None`` if the key is invalid/inactive or any link
        in the chain is missing.
        """
        api_key = await self.get_api_key_object(plain_key)
        if not api_key:
            return None

        await self._api_keys.increment_usage(api_key.id)

        project = await self._projects.get_by_id(api_key.project_id)
        if not project:
            return None

        organization = await self._organizations.get_by_id(project.organization_id)
        if not organization:
            return None

        user = await self._users.get_by_id(organization.owner_id)
        if not user:
            return None

        return user, api_key

    async def verify_api_key(self, plain_key: str) -> User | None:
        """Validate an API key and resolve it to the authenticated user."""
        ctx = await self.resolve_context(plain_key)
        return ctx[0] if ctx else None

    async def get_api_key_object(self, plain_key: str) -> APIKey | None:
        """Resolve a plain API key to its APIKey object if valid and active."""
        if not plain_key.startswith("sk_") or len(plain_key) != 35:
            return None

        prefix = self.get_key_prefix(plain_key)

        api_key = await self._api_keys.get_by_prefix(prefix)
        if not api_key or not api_key.is_active:
            return None

        try:
            is_valid = _password_hash.verify(plain_key, api_key.key_hash)
        except Exception:
            return None

        if not is_valid:
            return None

        return api_key

    async def list_project_keys(
        self,
        project_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> list[APIKey]:
        keys = await self._api_keys.get_by_project_id(
            project_id,
            include_inactive=include_inactive,
        )
        return list(keys)

    async def delete_api_key(self, key_id: UUID, project_id: UUID) -> None:
        api_key = await self._api_keys.get_by_id(key_id)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API ключ не найден",
            )

        if api_key.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для удаления этого ключа",
            )

        await self._api_keys.delete(key_id)

    async def get_key_details(self, key_id: UUID, project_id: UUID) -> APIKey:
        api_key = await self._api_keys.get_by_id(key_id)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API ключ не найден",
            )

        if api_key.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для просмотра этого ключа",
            )

        return api_key
