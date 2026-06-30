"""
Auth REST endpoints: registration and login.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from assemblix_api.billing.rate_limit_backends import (
    InMemoryRateLimitBackend,
    RateLimitBackend,
    RedisRateLimitBackend,
)
from assemblix_api.core.redis_client import get_redis, is_redis_enabled
from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_current_user,
    get_oauth_service,
    get_user_service,
)
from assemblix_api.dto.requests.auth import (
    LoginRequest,
    OAuthTokenRequest,
    RegisterOrLoginRequest,
    RegisterRequest,
    UpdateUserRequest,
)
from assemblix_api.dto.responses.auth import (
    RegisterOrLoginResponse,
    RegisterResponse,
    TokenResponse,
    UserPublic,
)
from assemblix_api.enums import OAuthProvider
from assemblix_api.services.oauth_service import OAuthService
from assemblix_api.services.user_service import UserService

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])

# Process-level singleton — created once so the in-memory sliding window
# is not reset between requests. Reset to None only in tests.
_rate_limit_backend: RateLimitBackend | None = None


async def _get_rate_limit_backend() -> RateLimitBackend:
    """Return the process-wide rate-limit backend, initialising it on first call."""
    global _rate_limit_backend
    if _rate_limit_backend is None:
        if is_redis_enabled():
            redis = await get_redis()
            _rate_limit_backend = RedisRateLimitBackend(redis)
        else:
            _rate_limit_backend = InMemoryRateLimitBackend()
    return _rate_limit_backend


def _client_ip(request: Request) -> str:
    """Derive the real client IP, honouring the X-Forwarded-For header.

    Takes the first (leftmost) entry from X-Forwarded-For when present; falls
    back to the TCP peer address.  This trusts the proxy's XFF header, which is
    acceptable because the app is expected to run behind a trusted reverse proxy
    — matching the behaviour of the prior core/login_rate_limit.py module.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _enforce_login_rate_limit(
    backend: RateLimitBackend,
    ip: str,
    limit: int,
    window_seconds: int = 300,
) -> None:
    """Check one auth attempt from *ip* against *backend*.

    Raises HTTPException 429 when the backend denies the hit (window exceeded).
    Default window is 300 s (5 minutes), matching the original 10/5 min policy.
    """
    allowed = await backend.hit(key=f"auth:{ip}", limit=limit, window_seconds=window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts, try again later",
            headers={"Retry-After": "300"},
        )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> RegisterResponse:
    """Register a new user and return an access token with default org/project IDs."""
    ip = _client_ip(request)
    backend = await _get_rate_limit_backend()
    await _enforce_login_rate_limit(backend, ip=ip, limit=settings.login_rate_limit_per_5min)
    user, token, organization_id, project_id = await user_service.register_and_login(
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        company_name=payload.company_name,
        is_test=payload.is_test,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
    )
    return RegisterResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        organization_id=organization_id,
        project_id=project_id,
    )


@router.post(
    "/register-or-login",
    response_model=RegisterOrLoginResponse,
    status_code=status.HTTP_200_OK,
)
async def register_or_login(
    payload: RegisterOrLoginRequest,
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> RegisterOrLoginResponse:
    """Universal auth endpoint: register a new user or log in an existing one.

    Outcomes: registered, logged_in, account_exists, oauth_account.
    """
    ip = _client_ip(request)
    backend = await _get_rate_limit_backend()
    await _enforce_login_rate_limit(backend, ip=ip, limit=settings.login_rate_limit_per_5min)
    result = await user_service.register_or_login(data=payload)
    return RegisterOrLoginResponse(
        action=result.action,
        access_token=result.token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60 if result.token else None,
        organization_id=result.organization_id,
        project_id=result.project_id,
        provider=result.provider,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    payload: LoginRequest,
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> TokenResponse:
    """Authenticate a user and return an access token."""
    ip = _client_ip(request)
    backend = await _get_rate_limit_backend()
    await _enforce_login_rate_limit(backend, ip=ip, limit=settings.login_rate_limit_per_5min)
    token = await user_service.login(email=str(payload.email), password=payload.password)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPublic:
    """Return the authenticated user. Requires a Bearer token."""
    return UserPublic.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
)
async def update_current_user(
    payload: UpdateUserRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: UserService = Depends(get_user_service),
) -> UserPublic:
    """
    Update the current user. Requires a Bearer token.

    Only the provided fields are updated (full_name, company_name, onboarding).
    """
    updated_user = await user_service.update_user(
        current_user,
        full_name=payload.full_name,
        company_name=payload.company_name,
        onboarding=payload.onboarding,
    )
    return UserPublic.model_validate(updated_user)


@router.post(
    "/oauth/{provider}",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
async def oauth_authenticate(
    provider: OAuthProvider,
    payload: OAuthTokenRequest,
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> TokenResponse:
    """
    Authenticate via an OAuth provider.

    The frontend sends the provider's ID token; the backend verifies it and
    creates or finds the matching user.

    Supported providers:
    - google: Google Sign-In
    """
    user, token = await oauth_service.authenticate(provider.value, payload.id_token)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )
