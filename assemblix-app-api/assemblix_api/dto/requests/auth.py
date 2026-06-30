"""
Pydantic schemas for registration/login.
"""

from __future__ import annotations

from typing import Any

from pydantic import EmailStr, Field

from assemblix_api.dto.base import DTOModel


class RegisterRequest(DTOModel):
    email: EmailStr = Field(description="User email address used as the login identifier")
    password: str = Field(
        min_length=4,
        max_length=128,
        description="User password, must be 4-128 characters",
    )
    full_name: str | None = Field(
        default=None, max_length=255, description="Full name of the user (optional)"
    )
    company_name: str | None = Field(
        default=None,
        max_length=255,
        description="Name of the user's company or organization (optional)",
    )
    is_test: bool = Field(
        default=False,
        description="If true, marks the account as a test account (used for internal testing)",
    )

    # UTM tracking (all optional)
    utm_source: str | None = Field(
        default=None,
        max_length=255,
        description="UTM source parameter identifying which site sent the traffic (e.g. google, newsletter)",
    )
    utm_medium: str | None = Field(
        default=None,
        max_length=255,
        description="UTM medium parameter identifying the marketing medium (e.g. cpc, email, social)",
    )
    utm_campaign: str | None = Field(
        default=None,
        max_length=255,
        description="UTM campaign parameter identifying the specific campaign name or promotion",
    )
    utm_content: str | None = Field(
        default=None,
        max_length=255,
        description="UTM content parameter used to differentiate ads or links pointing to the same URL",
    )
    utm_term: str | None = Field(
        default=None,
        max_length=255,
        description="UTM term parameter identifying paid search keywords",
    )


class RegisterOrLoginRequest(DTOModel):
    """Combined register-or-login request."""

    email: EmailStr = Field(
        description="User email address; if the account exists the user is logged in, otherwise a new account is created"
    )
    password: str = Field(
        min_length=1,
        max_length=128,
        description="User password, must be 1-128 characters",
    )
    full_name: str | None = Field(
        default=None,
        max_length=255,
        description="Full name of the user, used only during registration (ignored for existing accounts)",
    )
    company_name: str | None = Field(
        default=None,
        max_length=255,
        description="Company or organization name, used only during registration (ignored for existing accounts)",
    )
    is_test: bool = Field(
        default=False,
        description="If true, marks the account as a test account (used for internal testing)",
    )

    # UTM tracking
    utm_source: str | None = Field(
        default=None,
        max_length=255,
        description="UTM source parameter identifying which site sent the traffic",
    )
    utm_medium: str | None = Field(
        default=None,
        max_length=255,
        description="UTM medium parameter identifying the marketing medium (e.g. cpc, email)",
    )
    utm_campaign: str | None = Field(
        default=None,
        max_length=255,
        description="UTM campaign parameter identifying the specific campaign or promotion",
    )
    utm_content: str | None = Field(
        default=None,
        max_length=255,
        description="UTM content parameter used to differentiate ads or links pointing to the same URL",
    )
    utm_term: str | None = Field(
        default=None,
        max_length=255,
        description="UTM term parameter identifying paid search keywords",
    )


class LoginRequest(DTOModel):
    email: EmailStr = Field(description="Email address of the account to log in to")
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Account password, must be 1-128 characters",
    )


class UpdateUserRequest(DTOModel):
    """
    Schema for updating user data (PATCH /auth/me).

    All fields are optional - only provided ones are updated.
    """

    full_name: str | None = Field(
        default=None,
        max_length=255,
        description="Updated full name of the user; pass null to leave unchanged",
    )
    company_name: str | None = Field(
        default=None,
        max_length=255,
        description="Updated company or organization name; pass null to leave unchanged",
    )
    onboarding: dict[str, Any] | None = Field(
        default=None,
        description="Onboarding progress data as a JSON object; merged with existing onboarding state",
    )


class OAuthTokenRequest(DTOModel):
    """
    Schema for OAuth authentication.

    The frontend sends an ID token from an OAuth provider (Google, GitHub, etc.).
    """

    id_token: str = Field(..., description="ID token from the OAuth provider")
