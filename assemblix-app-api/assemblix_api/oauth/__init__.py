"""OAuth providers for authentication."""

from assemblix_api.oauth.base import BaseOAuthProvider
from assemblix_api.oauth.google import GoogleOAuthProvider
from assemblix_api.oauth.registry import OAuthProviderRegistry
from assemblix_api.oauth.schemas import OAuthUserInfo

__all__ = [
    "BaseOAuthProvider",
    "GoogleOAuthProvider",
    "OAuthProviderRegistry",
    "OAuthUserInfo",
]
