"""Google OAuth Provider.

Authorization code flow: the frontend obtains an authorization code from Google via a
popup (@react-oauth/google useGoogleLogin flow='auth-code'); the backend exchanges it
for an id_token and verifies it.
"""

import httpx
from fastapi import HTTPException, status
from google.auth.transport import requests
from google.oauth2 import id_token

from assemblix_api.oauth.base import BaseOAuthProvider
from assemblix_api.oauth.schemas import OAuthUserInfo

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleOAuthProvider(BaseOAuthProvider):
    """Google OAuth provider: exchanges an authorization code for an id_token, then verifies it."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    async def verify_token(self, token: str) -> OAuthUserInfo:
        """Exchange the authorization code for an id_token, verify it, and return user info."""
        id_token_str = await self._exchange_code_for_id_token(token)

        try:
            idinfo = id_token.verify_oauth2_token(id_token_str, requests.Request(), self.client_id)

            if idinfo["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Неверный issuer токена",
                )

            return OAuthUserInfo(
                provider="google",
                provider_user_id=idinfo["sub"],
                email=idinfo["email"],
                email_verified=idinfo.get("email_verified", False),
                full_name=idinfo.get("name"),
                avatar_url=idinfo.get("picture"),
            )

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Невалидный Google id_token: {str(e)}",
            ) from e

    async def _exchange_code_for_id_token(self, code: str) -> str:
        """Exchange the authorization code for an id_token via the Google token endpoint.

        redirect_uri='postmessage' is a special value Google uses for popup flows
        (@react-oauth/google auth-code flow opens a popup and receives the code via postMessage).
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": "postmessage",
                    "grant_type": "authorization_code",
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Не удалось обменять Google код на токен: {response.text}",
            )

        payload = response.json()
        id_token_value = payload.get("id_token")
        if not id_token_value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google не вернул id_token",
            )
        return id_token_value
