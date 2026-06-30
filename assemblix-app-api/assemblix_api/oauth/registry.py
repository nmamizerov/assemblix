"""OAuth provider registry."""

from fastapi import HTTPException, status

from assemblix_api.oauth.base import BaseOAuthProvider


class OAuthProviderRegistry:
    """Registry mapping provider names to registered OAuth provider instances."""

    _providers: dict[str, BaseOAuthProvider] = {}

    @classmethod
    def register(cls, name: str, provider: BaseOAuthProvider) -> None:
        cls._providers[name] = provider

    @classmethod
    def get(cls, name: str) -> BaseOAuthProvider:
        """Return the provider by name, raising HTTPException if not registered."""
        if name not in cls._providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неизвестный OAuth провайдер: {name}",
            )
        return cls._providers[name]

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._providers
