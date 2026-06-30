"""
OAuth Service - OAuth authentication business logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException, status

from assemblix_api.billing.plans import get_default_plan, get_plan_config
from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.user import User
from assemblix_api.database.repositories.organization_repository import (
    OrganizationRepository,
)
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.database.repositories.project_repository import ProjectRepository
from assemblix_api.database.repositories.user_repository import UserRepository
from assemblix_api.oauth.registry import OAuthProviderRegistry
from assemblix_api.oauth.schemas import OAuthUserInfo

settings = get_settings()


class OAuthService:
    """OAuth authentication: verify provider tokens, find/create users, issue JWTs."""

    def __init__(
        self,
        user_repository: UserRepository,
        organization_repository: OrganizationRepository | None = None,
        organization_user_repository: OrganizationUserRepository | None = None,
        project_repository: ProjectRepository | None = None,
    ):
        self._users = user_repository
        self._organizations = organization_repository
        self._org_users = organization_user_repository
        self._projects = project_repository

    async def authenticate(self, provider: str, id_token: str) -> tuple[User, str]:
        """
        Authenticate via an OAuth provider, returning (User, JWT token).

        Verify the provider token, look up the user by provider + provider_user_id,
        and create one if absent. Raises HTTPException on verification failure or if
        the email is already registered through another method (email collision).
        """
        oauth_provider = OAuthProviderRegistry.get(provider)
        user_info = await oauth_provider.verify_token(id_token)

        if not user_info.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email не подтвержден у провайдера",
            )

        user = await self._users.get_by_provider(provider, user_info.provider_user_id)

        if user:
            await self._users.touch_last_login(user)
            return user, self._create_access_token(user_id=user.id, email=user.email)

        # Reject if the email is already registered through another auth method.
        existing = await self._users.get_by_email(user_info.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email уже зарегистрирован. Войдите через пароль или другой метод.",
            )

        user = await self._create_oauth_user(user_info)
        token = self._create_access_token(user_id=user.id, email=user.email)

        return user, token

    async def _create_oauth_user(self, user_info: OAuthUserInfo) -> User:
        user = await self._users.create_oauth_user(
            email=user_info.email,
            auth_provider=user_info.provider,
            provider_user_id=user_info.provider_user_id,
            full_name=user_info.full_name,
            avatar_url=user_info.avatar_url,
        )

        if self._organizations and self._org_users and self._projects:
            await self._create_personal_organization_and_project(user)

        return user

    async def _create_personal_organization_and_project(self, user: User) -> None:
        """Create the user's personal organization and a default project."""
        from uuid import uuid4

        # Guaranteed non-None by the caller's `if self._organizations and ...` guard.
        assert self._organizations is not None
        assert self._org_users is not None
        assert self._projects is not None

        default_plan = get_default_plan()
        plan_config = get_plan_config(default_plan)

        org_slug = f"personal-{str(uuid4())[:8]}"
        organization = await self._organizations.create(
            name=f"Personal ({user.email})",
            slug=org_slug,
            owner_id=user.id,
            is_personal=True,
            plan=default_plan,
            chat_plan=default_plan,
            credits_balance=plan_config.credits_per_month,
            credits_period_start=datetime.utcnow().date(),
        )

        await self._org_users.create(
            organization_id=organization.id,
            user_id=user.id,
            is_owner=True,
        )

        await self._projects.create(
            organization_id=organization.id,
            name="Default Project",
            slug="default",
            description="Your default project",
        )

        await self._users.update(
            user,
            current_organization_id=organization.id,
        )

    def _create_access_token(self, *, user_id: UUID, email: str) -> str:
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
