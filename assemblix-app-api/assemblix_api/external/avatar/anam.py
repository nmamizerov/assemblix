"""Direct anam.ai client: avatar listing and session-token minting.

anam has its own API (not OpenAI-compatible). The session token lets the browser
SDK connect over WebRTC without exposing the API key. llmId=CUSTOMER_CLIENT_V1
disables anam's brain so the avatar only speaks text we push client-side.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from assemblix_api.core.settings import get_settings

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _base_url() -> str:
    return get_settings().anam_api_base_url.rstrip("/")


def _client() -> httpx.AsyncClient:
    """Factory kept as a seam so tests can inject a MockTransport."""
    return httpx.AsyncClient(timeout=_TIMEOUT)


class AnamAvatar(BaseModel):
    id: str
    name: str


def _avatar_label(item: dict) -> str:
    """Human label from an anam avatar item: 'displayName (variantName)'.

    anam avatars carry ``displayName`` + optional ``variantName`` (there is no
    single ``name`` field); the variant disambiguates same-named avatars.
    """
    display = item.get("displayName") or item["id"]
    variant = item.get("variantName")
    return f"{display} ({variant})" if variant else display


async def list_avatars(api_key: str) -> list[AnamAvatar]:
    """Return the avatars available to ``api_key`` (GET /v1/avatars)."""
    async with _client() as client:
        resp = await client.get(
            f"{_base_url()}/v1/avatars", headers={"Authorization": f"Bearer {api_key}"}
        )
        resp.raise_for_status()
        data = resp.json()
    return [AnamAvatar(id=a["id"], name=_avatar_label(a)) for a in data.get("data", [])]


async def mint_session_token(*, api_key: str, persona_config: dict) -> str:
    """Exchange the API key for a short-lived client session token."""
    async with _client() as client:
        resp = await client.post(
            f"{_base_url()}/v1/auth/session-token",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"personaConfig": persona_config},
        )
        resp.raise_for_status()
        return resp.json()["sessionToken"]
