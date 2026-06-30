"""
Pydantic schemas for registration/login
"""

from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field

from assemblix_api.dto.base import DTOModel


class TokenResponse(DTOModel):
    access_token: str = Field(
        description="JWT access token for authenticating subsequent API requests"
    )
    token_type: str = Field(default="bearer", description="Token type, always 'bearer'")
    expires_in: int | None = Field(
        default=None, description="Token expiration time in seconds, if applicable"
    )


class RegisterResponse(TokenResponse):
    """
    Registration response — extends TokenResponse with the IDs of the
    organization and project created during registration.
    """

    organization_id: UUID | None = Field(
        default=None, description="ID of the organization created during registration"
    )
    project_id: UUID | None = Field(
        default=None,
        description="ID of the default project created during registration",
    )


class RegisterOrLoginResponse(DTOModel):
    """Response for the register-or-login flow."""

    action: str = Field(
        description="Result action: 'registered', 'logged_in', 'account_exists', or 'oauth_account'"
    )
    access_token: str | None = Field(
        default=None,
        description="JWT access token, present when login or registration succeeds",
    )
    token_type: str = Field(default="bearer", description="Token type, always 'bearer'")
    expires_in: int | None = Field(
        default=None, description="Token expiration time in seconds, if applicable"
    )
    organization_id: UUID | None = Field(
        default=None,
        description="ID of the user's organization, present on successful registration or login",
    )
    project_id: UUID | None = Field(
        default=None,
        description="ID of the user's default project, present on successful registration or login",
    )
    provider: str | None = Field(
        default=None,
        description="OAuth provider name (e.g. 'google') if the account uses OAuth authentication",
    )


class UserPublic(DTOModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier of the user")
    email: EmailStr = Field(description="User's email address")
    full_name: str | None = Field(default=None, description="User's full display name")
    company_name: str | None = Field(
        default=None, description="Name of the user's company or organization"
    )
    onboarding: dict = Field(
        default={}, description="Onboarding progress and preferences as a key-value map"
    )
    is_active: bool = Field(description="Whether the user account is currently active")
    is_verified: bool = Field(description="Whether the user's email has been verified")
    avatar_url: str | None = Field(default=None, description="URL of the user's avatar image")
    auth_provider: str | None = Field(
        default=None,
        description="Authentication provider used (e.g. 'google', 'email')",
    )
