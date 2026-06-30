"""User repository - database operations for users."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.user import User


class UserRepository:
    """Repository for the users table."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str | None = None,
        company_name: str | None = None,
        is_test: bool = False,
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        utm_term: str | None = None,
    ) -> User:
        user = User(
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
        self._session.add(user)
        # commit is handled by the get_session() dependency
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def touch_last_login(self, user: User) -> None:
        user.last_login_at = datetime.utcnow()
        self._session.add(user)

    async def update(self, user: User, **kwargs) -> User:
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def get_by_provider(self, provider: str, provider_user_id: str) -> User | None:
        """Get a user by OAuth provider and provider-side user ID."""
        stmt = select(User).where(
            User.auth_provider == provider, User.provider_user_id == provider_user_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_oauth_user(
        self,
        *,
        email: str,
        auth_provider: str,
        provider_user_id: str,
        full_name: str | None = None,
        avatar_url: str | None = None,
        is_test: bool = False,
    ) -> User:
        """Create an OAuth user (without a password)."""
        user = User(
            email=email,
            password_hash=None,  # OAuth users have no password
            auth_provider=auth_provider,
            provider_user_id=provider_user_id,
            full_name=full_name,
            avatar_url=avatar_url,
            is_test=is_test,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def delete_test_users(self) -> int:
        """Delete all test users (is_test=True)."""
        stmt = delete(User).where(User.is_test == True)
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]  # rowcount available on CursorResult for DML statements
