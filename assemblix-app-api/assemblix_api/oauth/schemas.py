"""OAuth data schemas."""

from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    """User information returned by an OAuth provider."""

    provider: str
    provider_user_id: str
    email: str
    email_verified: bool
    full_name: str | None = None
    avatar_url: str | None = None
