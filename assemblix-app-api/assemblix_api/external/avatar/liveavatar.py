"""Direct LiveAvatar (HeyGen) client: avatar listing and LITE sessions in our LiveKit room.

LITE mode renders the face only: the avatar joins our room to publish video, and
our pipeline drives it with audio over the session socket (see liveavatar_socket).
A session bills until it is stopped, so every started session gets a stop.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, status
from pydantic import BaseModel

from assemblix_api.core.settings import get_settings
from assemblix_api.external.avatar.base import VendorSession
from assemblix_api.external.avatar.errors import AvatarBusy, AvatarUnavailable
from assemblix_api.external.avatar.liveavatar_socket import LiveAvatarSocketOutput, connect_socket

logger = structlog.get_logger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_PAGE_SIZE = 100


def _client() -> httpx.AsyncClient:
    """Factory kept as a seam so tests can inject a MockTransport."""
    return httpx.AsyncClient(timeout=_TIMEOUT)


def _base_url() -> str:
    return get_settings().liveavatar_api_base_url.rstrip("/")


class LiveAvatarAvatar(BaseModel):
    id: str
    name: str


def _describe(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return f"{resp.status_code} code={body.get('code')}: {body.get('message')}"
    except ValueError:
        return f"{resp.status_code}: {resp.text[:500]}"


async def list_avatars(api_key: str) -> list[LiveAvatarAvatar]:
    """Return the account's own avatars, then the stock ones; only usable ones."""
    avatars: list[LiveAvatarAvatar] = []
    async with _client() as client:
        for path in ("/v1/avatars", "/v1/avatars/public"):
            resp = await client.get(
                f"{_base_url()}{path}",
                headers={"X-API-KEY": api_key},
                params={"page": 1, "page_size": _PAGE_SIZE},
            )
            if not resp.is_success:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"liveavatar avatar listing failed ({_describe(resp)})",
                )
            for item in (resp.json().get("data") or {}).get("results") or []:
                if item.get("status") == "ACTIVE" and not item.get("is_expired"):
                    avatars.append(
                        LiveAvatarAvatar(id=item["id"], name=item.get("name") or item["id"])
                    )
    return avatars


def _raise_for_session(resp: httpx.Response, action: str) -> None:
    if resp.is_success:
        return
    message = f"liveavatar {action} failed ({_describe(resp)})"
    if resp.status_code == 429:
        raise AvatarBusy(message)
    raise AvatarUnavailable(message)


async def _stop(session_id: str, session_token: str, reason: str) -> None:
    try:
        async with _client() as client:
            resp = await client.post(
                f"{_base_url()}/v1/sessions/stop",
                headers={"Authorization": f"Bearer {session_token}"},
                json={"session_id": session_id, "reason": reason},
            )
        if not resp.is_success:
            logger.warning("liveavatar.stop_failed", session_id=session_id, error=_describe(resp))
    except httpx.HTTPError as exc:
        logger.warning("liveavatar.stop_failed", session_id=session_id, error=str(exc))


async def start_livekit_session(
    *,
    api_key: str,
    avatar_id: str,
    livekit_url: str,
    room_name: str,
    make_livekit_token: Callable[[dict[str, str]], str],
) -> VendorSession:
    settings = get_settings()
    payload = {
        "mode": "LITE",
        "avatar_id": avatar_id,
        "is_sandbox": settings.liveavatar_sandbox,
        "video_settings": {"quality": "high", "encoding": "H264"},
        "livekit_config": {
            "livekit_url": livekit_url,
            "livekit_room": room_name,
            "livekit_client_token": make_livekit_token({}),
        },
    }
    try:
        async with _client() as client:
            resp = await client.post(
                f"{_base_url()}/v1/sessions/token",
                headers={"X-API-KEY": api_key},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise AvatarUnavailable(f"liveavatar is unreachable: {exc}") from exc
    _raise_for_session(resp, "session token")
    data = resp.json()["data"]
    session_id: str = data["session_id"]
    session_token: str = data["session_token"]

    output: LiveAvatarSocketOutput | None = None
    try:
        async with _client() as client:
            resp = await client.post(
                f"{_base_url()}/v1/sessions/start",
                headers={"Authorization": f"Bearer {session_token}"},
                json={"session_id": session_id},
            )
        _raise_for_session(resp, "session start")
        ws: Any = await connect_socket(resp.json()["data"]["ws_url"])
        output = LiveAvatarSocketOutput(ws)
        await output.wait_connected()
    except BaseException as exc:
        if output is not None:
            await output.aclose()
        await _stop(session_id, session_token, "SERVER_ERROR")
        if isinstance(exc, httpx.HTTPError | OSError):
            raise AvatarUnavailable(f"liveavatar session start failed: {exc}") from exc
        raise

    socket_output = output

    async def stop() -> None:
        with contextlib.suppress(Exception):
            await socket_output.aclose()
        await _stop(session_id, session_token, "USER_DISCONNECTED")

    return VendorSession(session_id=session_id, output=socket_output, stop=stop)
