"""Direct bitHuman client: agent listing and cloud avatars in our LiveKit room.

The cloud avatar reads its credentials from the attributes of its LiveKit token,
which every room participant can see, so it only ever gets a room-scoped token
minted per call — never the account secret.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from assemblix_api.core.settings import get_settings
from assemblix_api.external.avatar.errors import AvatarBusy, AvatarUnavailable

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _client() -> httpx.AsyncClient:
    """Factory kept as a seam so tests can inject a MockTransport."""
    return httpx.AsyncClient(timeout=_TIMEOUT)


def _base_url() -> str:
    return get_settings().bithuman_api_base_url.rstrip("/")


class BithumanAvatar(BaseModel):
    id: str
    name: str
    supported_models: list[str]


async def list_avatars(api_key: str) -> list[BithumanAvatar]:
    """Return the account's ready agents (GET /v1/agents)."""
    async with _client() as client:
        resp = await client.get(
            f"{_base_url()}/v1/agents",
            headers={"api-secret": api_key},
            params={"status": "ready", "limit": 100},
        )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"bithuman agent listing failed ({resp.status_code}): {resp.text[:500]}",
        )
    return [
        BithumanAvatar(
            id=item["code"],
            name=item.get("name") or item["code"],
            supported_models=item.get("supported_models") or [],
        )
        for item in resp.json().get("data") or []
    ]


def _error_code(resp: httpx.Response) -> str:
    try:
        return str(resp.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return ""


def _raise_for_start(resp: httpx.Response, action: str) -> None:
    if resp.is_success:
        return
    detail = f"bithuman {action} failed ({resp.status_code}): {resp.text[:500]}"
    if resp.status_code == 429 or _error_code(resp) == "CONCURRENCY_LIMIT_REACHED":
        raise AvatarBusy(detail)
    raise AvatarUnavailable(detail)


async def start_livekit_session(
    *,
    api_key: str,
    avatar_id: str,
    avatar_model: str,
    livekit_url: str,
    room_name: str,
    make_livekit_token: Callable[[dict[str, str]], str],
) -> str:
    """Start a cloud avatar that joins ``room_name`` as the avatar participant."""
    settings = get_settings()
    try:
        async with _client() as client:
            mint = await client.post(
                f"{_base_url()}/v1/runtime-tokens/mint",
                headers={"api-secret": api_key},
                json={
                    "agent_code": avatar_id,
                    "scope": "livekit-cloud",
                    "room_name": room_name,
                    "livekit_url": livekit_url,
                },
            )
            _raise_for_start(mint, "token minting")
            scoped = mint.json().get("scoped_token")
            if not scoped:
                raise AvatarUnavailable("bithuman token minting returned no scoped_token")
            start = await client.post(
                settings.bithuman_runtime_url,
                headers={"api-secret": scoped},
                json={
                    "livekit_url": livekit_url,
                    "livekit_token": make_livekit_token(
                        {"agent_id": avatar_id, "api_secret": scoped}
                    ),
                    "room_name": room_name,
                    "agent_id": avatar_id,
                    "model": avatar_model,
                    # Legacy engine hint the cloud API still reads.
                    "mode": "gpu" if avatar_model.startswith("expression") else "cpu",
                },
            )
            _raise_for_start(start, "cloud session")
    except httpx.HTTPError as exc:
        raise AvatarUnavailable(f"bithuman unreachable: {exc}") from exc
    return ""
