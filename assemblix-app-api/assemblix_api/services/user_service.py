"""
User service - registration/login business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException, status
from jwt import ExpiredSignatureError, PyJWTError
from pwdlib import PasswordHash

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

if TYPE_CHECKING:
    from assemblix_api.dto.requests.auth import RegisterOrLoginRequest

settings = get_settings()

_password_hash = PasswordHash.recommended()


@dataclass(frozen=True)
class TokenData:
    sub: str


@dataclass(frozen=True)
class RegisterOrLoginResult:
    action: str  # "registered", "logged_in", "account_exists", "oauth_account"
    token: str | None = None
    organization_id: UUID | None = None
    project_id: UUID | None = None
    provider: str | None = None


class UserService:
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

    async def register_user(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
        company_name: str | None = None,
        is_test: bool = False,
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        utm_term: str | None = None,
    ) -> tuple[User, UUID | None, UUID | None]:
        """
        Register a new user, returning (user, organization_id, project_id).

        organization_id and project_id are None when the org/project repositories
        were not supplied to the service.
        """
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email уже зарегистрирован",
            )

        password_hash = _password_hash.hash(password)
        user = await self._users.create_user(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            company_name=company_name,
            is_test=is_test,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
            utm_term=utm_term,
        )

        organization_id: UUID | None = None
        project_id: UUID | None = None

        if self._organizations and self._org_users and self._projects:
            organization_id, project_id = await self._create_personal_organization_and_project(user)

        return user, organization_id, project_id

    async def _create_personal_organization_and_project(self, user: User) -> tuple[UUID, UUID]:
        """Create the user's personal organization and a default project."""
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

        project = await self._projects.create(
            organization_id=organization.id,
            name="Default Project",
            slug="default",
            description="Your default project",
        )

        await self._users.update(
            user,
            current_organization_id=organization.id,
        )

        return organization.id, project.id

    async def register_and_login(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
        company_name: str | None = None,
        is_test: bool = False,
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        utm_term: str | None = None,
    ) -> tuple[User, str, UUID | None, UUID | None]:
        """Register a user and immediately issue an access token."""
        user, organization_id, project_id = await self.register_user(
            email=email,
            password=password,
            full_name=full_name,
            company_name=company_name,
            is_test=is_test,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
            utm_term=utm_term,
        )

        token = self._create_access_token(user_id=user.id, email=user.email)

        return user, token, organization_id, project_id

    async def register_or_login(
        self,
        *,
        data: RegisterOrLoginRequest,
    ) -> RegisterOrLoginResult:
        """
        Unified endpoint that either registers or logs the user in.

        - User does not exist: register + auto-login.
        - Exists via OAuth: returns oauth_account.
        - Exists with wrong password: returns account_exists.
        - Exists with correct password: logs in.
        """
        existing = await self._users.get_by_email(str(data.email))

        if existing is None:
            user, organization_id, project_id = await self.register_user(
                email=str(data.email),
                password=data.password,
                full_name=data.full_name,
                company_name=data.company_name,
                is_test=data.is_test,
                utm_source=data.utm_source,
                utm_medium=data.utm_medium,
                utm_campaign=data.utm_campaign,
                utm_content=data.utm_content,
                utm_term=data.utm_term,
            )
            token = self._create_access_token(user_id=user.id, email=user.email)
            return RegisterOrLoginResult(
                action="registered",
                token=token,
                organization_id=organization_id,
                project_id=project_id,
            )

        # OAuth users cannot log in with a password.
        if existing.auth_provider is not None and not existing.password_hash:
            return RegisterOrLoginResult(
                action="oauth_account",
                provider=existing.auth_provider,
            )

        if existing.password_hash is None or not _password_hash.verify(
            data.password, existing.password_hash
        ):
            return RegisterOrLoginResult(action="account_exists")

        if not existing.is_active:
            return RegisterOrLoginResult(action="account_exists")

        await self._users.touch_last_login(existing)
        token = self._create_access_token(user_id=existing.id, email=existing.email)
        return RegisterOrLoginResult(
            action="logged_in",
            token=token,
            organization_id=existing.current_organization_id,
        )

    async def login(self, *, email: str, password: str) -> str:
        user = await self._users.get_by_email(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        # Block password login for OAuth users.
        if user.auth_provider is not None and not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Используйте вход через {user.auth_provider}",
            )

        if user.password_hash is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        if not _password_hash.verify(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь деактивирован",
            )

        await self._users.touch_last_login(user)

        return self._create_access_token(user_id=user.id, email=user.email)

    def decode_and_validate_token(self, token: str) -> TokenData:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={
                    "require": ["exp", "iat", "sub"],
                },
            )
        except ExpiredSignatureError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Токен истёк",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не удалось проверить токен",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный токен",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(sub=sub)

    async def get_user_from_token(self, token: str) -> User:
        token_data = self.decode_and_validate_token(token)
        try:
            user_id = UUID(token_data.sub)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный subject в токене",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь деактивирован",
            )
        return user

    async def get_by_email(self, email: str) -> User | None:
        return await self._users.get_by_email(email)

    async def update_user(
        self,
        user: User,
        *,
        full_name: str | None = None,
        company_name: str | None = None,
        onboarding: dict | None = None,
    ) -> User:
        update_data: dict[str, Any] = {}

        if full_name is not None:
            update_data["full_name"] = full_name
        if company_name is not None:
            update_data["company_name"] = company_name
        if onboarding is not None:
            update_data["onboarding"] = onboarding

        if update_data:
            user = await self._users.update(user, **update_data)

        return user

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
