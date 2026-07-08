"""Direct anam.ai client: avatar listing and session-token minting.

anam has its own API (not OpenAI-compatible). The session token lets the browser
SDK connect over WebRTC without exposing the API key. llmId=CUSTOMER_CLIENT_V1
disables anam's brain so the avatar only speaks text we push client-side.
"""

from __future__ import annotations

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from assemblix_api.core.settings import get_settings

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _base_url() -> str:
    return get_settings().anam_api_base_url.rstrip("/")


def _client() -> httpx.AsyncClient:
    """Factory kept as a seam so tests can inject a MockTransport."""
    return httpx.AsyncClient(timeout=_TIMEOUT)


def _raise_for_anam(resp: httpx.Response, action: str) -> None:
    """Surface anam's response body on error instead of an opaque 500."""
    if resp.is_success:
        return
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"anam {action} failed ({resp.status_code}): {resp.text[:500]}",
    )


class AnamAvatar(BaseModel):
    id: str
    name: str


class AnamVoice(BaseModel):
    id: str
    name: str


def _items(payload: object) -> list[dict]:
    """anam list endpoints return either a bare array or a {"data": [...]} envelope."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
    return []


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
        _raise_for_anam(resp, "avatar listing")
        data = resp.json()
    return [AnamAvatar(id=a["id"], name=_avatar_label(a)) for a in _items(data)]


async def list_voices(api_key: str) -> list[AnamVoice]:
    """Return the voices available to ``api_key`` (GET /v1/voices)."""
    async with _client() as client:
        resp = await client.get(
            f"{_base_url()}/v1/voices", headers={"Authorization": f"Bearer {api_key}"}
        )
        _raise_for_anam(resp, "voice listing")
        data = resp.json()
    return [
        AnamVoice(id=v["id"], name=v.get("name") or v.get("displayName") or v["id"])
        for v in _items(data)
    ]


async def mint_session_token(*, api_key: str, persona_config: dict) -> str:
    """Exchange the API key for a short-lived client session token."""
    async with _client() as client:
        resp = await client.post(
            f"{_base_url()}/v1/auth/session-token",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"personaConfig": persona_config},
        )
        _raise_for_anam(resp, "session-token minting")
        body = resp.json()
    token = body.get("sessionToken")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"anam session-token response missing 'sessionToken': {str(body)[:500]}",
        )
    return token
