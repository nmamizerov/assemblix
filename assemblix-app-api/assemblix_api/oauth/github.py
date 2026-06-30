"""GitHub OAuth Provider.

Authorization code flow: the frontend receives a `code` after the GitHub redirect; the
backend exchanges it for an access_token and fetches the user profile.
"""

import httpx
from fastapi import HTTPException, status

from assemblix_api.oauth.base import BaseOAuthProvider
from assemblix_api.oauth.schemas import OAuthUserInfo

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubOAuthProvider(BaseOAuthProvider):
    """GitHub OAuth provider (authorization code flow).

    verify_token takes an authorization code, exchanges it for an access_token,
    and fetches the user's data.
    """

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    async def verify_token(self, token: str) -> OAuthUserInfo:
        """Exchange the authorization code for an access_token and return user info."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            access_token = await self._exchange_code(client, token)
            profile = await self._fetch_profile(client, access_token)
            email = profile.get("email") or await self._fetch_primary_email(client, access_token)

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub аккаунт не содержит подтвержденного email",
            )

        return OAuthUserInfo(
            provider="github",
            provider_user_id=str(profile["id"]),
            email=email,
            email_verified=True,  # /user/emails only returns verified primary emails
            full_name=profile.get("name") or profile.get("login"),
            avatar_url=profile.get("avatar_url"),
        )

    async def _exchange_code(self, client: httpx.AsyncClient, code: str) -> str:
        response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
            },
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не удалось обменять GitHub код на токен",
            )
        payload = response.json()
        if "error" in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"GitHub OAuth ошибка: {payload.get('error_description', payload['error'])}",
            )
        access_token = payload.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub не вернул access_token",
            )
        return access_token

    async def _fetch_profile(self, client: httpx.AsyncClient, access_token: str) -> dict:
        response = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не удалось получить профиль GitHub",
            )
        return response.json()

    async def _fetch_primary_email(
        self, client: httpx.AsyncClient, access_token: str
    ) -> str | None:
        response = await client.get(
            GITHUB_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if response.status_code != 200:
            return None
        for entry in response.json():
            if entry.get("primary") and entry.get("verified"):
                return entry.get("email")
        return None
