"""Anam joins a LiveKit room we own; failures become typed avatar errors."""

import json

import httpx
import pytest

from assemblix_api.external.avatar import anam
from assemblix_api.external.avatar.errors import AvatarBusy, AvatarUnavailable
from assemblix_api.external.avatar.livekit_join import start_vendor_session

_ARGS = dict(
    api_key="anam-key",
    avatar_id="av-1",
    avatar_model="cara-4",
    livekit_url="wss://rtc.example.com",
    livekit_token="lk-token",
)


def _mock(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(anam, "_client", lambda: httpx.AsyncClient(transport=transport))


async def test_posts_engine_session_with_room_environment(monkeypatch) -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"sessionId": "s-1", "region": "us"})

    _mock(monkeypatch, handler)

    session_id = await anam.start_livekit_session(**_ARGS)

    assert session_id == "s-1"
    assert captured["url"].endswith("/v1/engine/session")
    assert captured["auth"] == "Bearer anam-key"
    assert captured["body"] == {
        "personaConfig": {
            "type": "ephemeral",
            "name": "assemblix",
            "avatarId": "av-1",
            "avatarModel": "cara-4",
            "llmId": "CUSTOMER_CLIENT_V1",
        },
        "environment": {"livekitUrl": "wss://rtc.example.com", "livekitToken": "lk-token"},
    }


async def test_concurrency_limit_is_busy(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"reason": "concurrent_limit"})

    _mock(monkeypatch, handler)
    with pytest.raises(AvatarBusy):
        await anam.start_livekit_session(**_ARGS)


async def test_other_failures_are_unavailable(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    _mock(monkeypatch, handler)
    with pytest.raises(AvatarUnavailable):
        await anam.start_livekit_session(**_ARGS)


async def test_transport_errors_are_unavailable(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    _mock(monkeypatch, handler)
    with pytest.raises(AvatarUnavailable):
        await anam.start_livekit_session(**_ARGS)


async def test_dispatch_routes_anam_and_rejects_unknown(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"sessionId": "s-2"})

    _mock(monkeypatch, handler)
    assert await start_vendor_session(provider="anam", **_ARGS) == "s-2"
    with pytest.raises(AvatarUnavailable):
        await start_vendor_session(provider="nobody", **_ARGS)
