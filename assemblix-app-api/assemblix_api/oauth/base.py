"""Base protocol for OAuth providers."""

from typing import Protocol

from assemblix_api.oauth.schemas import OAuthUserInfo


class BaseOAuthProvider(Protocol):
    """Protocol for OAuth providers; each must implement verify_token."""

    async def verify_token(self, token: str) -> OAuthUserInfo:
        """Verify a provider token (id/access token) and return user info."""
        ...
