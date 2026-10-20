"""LiveAvatar LITE: session token, start, socket, stop, error mapping, listing."""

import asyncio
import json
from typing import Any

import httpx
import pytest
from fastapi import HTTPException

from assemblix_api.external.avatar import liveavatar
from assemblix_api.external.avatar.errors import AvatarBusy, AvatarUnavailable
from assemblix_api.external.avatar.liveavatar_socket import LiveAvatarSocketOutput
from assemblix_api.external.avatar.livekit_join import start_vendor_session

_ARGS = dict(
    api_key="la-key",
    avatar_id="av-1",
    livekit_url="wss://rtc.example.com",
    room_name="va-1",
)


class _Socket:
    def __init__(self, *, connects: bool = True) -> None:
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()
        self.closed = False
        if connects:
            self.incoming.put_nowait(
                json.dumps({"type": "session.state_updated", "state": "connected"})
            )
        else:
            self.incoming.put_nowait(None)

    async def send(self, data: str) -> None: ...

    def __aiter__(self) -> "_Socket":
        return self

    async def __anext__(self) -> str:
        item = await self.incoming.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self) -> None:
        self.closed = True


def _ok(data: Any) -> httpx.Response:
    return httpx.Response(200, json={"code": 100, "data": data, "message": "ok"})


def _mock(monkeypatch, handler, socket: _Socket | None = None) -> list[str]:
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(liveavatar, "_client", lambda: httpx.AsyncClient(transport=transport))
    opened: list[str] = []
    ws = socket or _Socket()

    async def connect(url: str) -> _Socket:
        opened.append(url)
        return ws

    monkeypatch.setattr(liveavatar, "connect_socket", connect)
    return opened


def _session_handler(calls: list[httpx.Request], *, start_status: int = 200):
    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/sessions/token"):
            return _ok({"session_id": "sess-1", "session_token": "st-1"})
        if path.endswith("/sessions/start"):
            if start_status != 200:
                return httpx.Response(start_status, json={"code": 5000, "message": "boom"})
            return _ok({"session_id": "sess-1", "ws_url": "wss://ws.liveavatar.com/s/1"})
        return _ok(None)

    return handler


def _token(extra: dict[str, str]) -> str:
    return "lk-token"


async def test_creates_token_then_starts_then_connects(monkeypatch) -> None:
    # Arrange
    calls: list[httpx.Request] = []
    opened = _mock(monkeypatch, _session_handler(calls))

    # Act
    session = await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)

    # Assert
    token_req, start_req = calls
    assert token_req.url.path == "/v1/sessions/token"
    assert token_req.headers["X-API-KEY"] == "la-key"
    assert json.loads(token_req.content) == {
        "mode": "LITE",
        "avatar_id": "av-1",
        "is_sandbox": False,
        "video_settings": {"quality": "high", "encoding": "H264"},
        "livekit_config": {
            "livekit_url": "wss://rtc.example.com",
            "livekit_room": "va-1",
            "livekit_client_token": "lk-token",
        },
    }
    assert start_req.url.path == "/v1/sessions/start"
    assert start_req.headers["Authorization"] == "Bearer st-1"
    assert json.loads(start_req.content) == {"session_id": "sess-1"}
    assert opened == ["wss://ws.liveavatar.com/s/1"]
    assert session.session_id == "sess-1"
    assert isinstance(session.output, LiveAvatarSocketOutput)
    assert session.stop is not None
    await session.stop()


async def test_token_gets_no_extra_attributes(monkeypatch) -> None:
    # Arrange
    _mock(monkeypatch, _session_handler([]))
    requested: list[dict[str, str]] = []

    def make(extra: dict[str, str]) -> str:
        requested.append(extra)
        return "lk-token"

    # Act
    session = await liveavatar.start_livekit_session(make_livekit_token=make, **_ARGS)

    # Assert
    assert requested == [{}]
    assert session.stop is not None
    await session.stop()


async def test_rate_limit_is_busy(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": 4290, "message": "Rate limit exceeded"})

    _mock(monkeypatch, handler)

    with pytest.raises(AvatarBusy):
        await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)


@pytest.mark.parametrize("status", [401, 422, 500])
async def test_other_errors_are_unavailable(monkeypatch, status: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"code": status * 10, "message": "nope"})

    _mock(monkeypatch, handler)

    with pytest.raises(AvatarUnavailable):
        await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)


async def test_transport_errors_are_unavailable(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    _mock(monkeypatch, handler)

    with pytest.raises(AvatarUnavailable):
        await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)


async def test_start_failure_stops_the_session(monkeypatch) -> None:
    # Arrange
    calls: list[httpx.Request] = []
    _mock(monkeypatch, _session_handler(calls, start_status=500))

    # Act
    with pytest.raises(AvatarUnavailable):
        await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)

    # Assert
    stop_req = calls[-1]
    assert stop_req.url.path == "/v1/sessions/stop"
    assert json.loads(stop_req.content) == {"session_id": "sess-1", "reason": "SERVER_ERROR"}


async def test_socket_that_never_connects_stops_the_session(monkeypatch) -> None:
    # Arrange
    calls: list[httpx.Request] = []
    _mock(monkeypatch, _session_handler(calls), socket=_Socket(connects=False))

    # Act
    with pytest.raises(AvatarUnavailable):
        await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)

    # Assert
    assert calls[-1].url.path == "/v1/sessions/stop"


async def test_stop_posts_user_disconnected_and_closes_socket(monkeypatch) -> None:
    # Arrange
    calls: list[httpx.Request] = []
    ws = _Socket()
    _mock(monkeypatch, _session_handler(calls), socket=ws)
    session = await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)
    assert session.stop is not None

    # Act
    await session.stop()

    # Assert
    stop_req = calls[-1]
    assert stop_req.url.path == "/v1/sessions/stop"
    assert stop_req.headers["Authorization"] == "Bearer st-1"
    assert json.loads(stop_req.content) == {"session_id": "sess-1", "reason": "USER_DISCONNECTED"}
    assert ws.closed


async def test_stop_errors_are_swallowed(monkeypatch) -> None:
    # Arrange
    ws = _Socket()
    started = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal started
        if request.url.path.endswith("/stop"):
            return httpx.Response(500, json={"code": 5000, "message": "boom"})
        started = True
        return await _session_handler([])(request)

    _mock(monkeypatch, handler, socket=ws)
    session = await liveavatar.start_livekit_session(make_livekit_token=_token, **_ARGS)
    assert session.stop is not None

    # Act
    await session.stop()

    # Assert
    assert started and ws.closed


async def test_list_avatars_custom_first_active_only(monkeypatch) -> None:
    # Arrange
    def avatar(id_: str, status: str = "ACTIVE", expired: bool = False) -> dict:
        return {"id": id_, "name": f"Avatar {id_}", "status": status, "is_expired": expired}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-KEY"] == "la-key"
        assert request.url.params["page_size"] == "100"
        if request.url.path == "/v1/avatars/public":
            results = [avatar("C"), avatar("D", expired=True)]
        else:
            results = [avatar("A"), avatar("B", status="FAILED")]
        return _ok({"count": 2, "next": None, "previous": None, "results": results})

    _mock(monkeypatch, handler)

    # Act
    avatars = await liveavatar.list_avatars("la-key")

    # Assert
    assert [(a.id, a.name) for a in avatars] == [("A", "Avatar A"), ("C", "Avatar C")]


async def test_list_avatars_error_is_bad_gateway(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": 4010, "message": "bad api key"})

    _mock(monkeypatch, handler)

    with pytest.raises(HTTPException) as exc:
        await liveavatar.list_avatars("la-key")
    assert exc.value.status_code == 502


async def test_dispatch_routes_liveavatar(monkeypatch) -> None:
    # Arrange
    _mock(monkeypatch, _session_handler([]))

    # Act
    session = await start_vendor_session(
        provider="liveavatar", avatar_model="lite", make_livekit_token=_token, **_ARGS
    )

    # Assert
    assert session.session_id == "sess-1"
    assert isinstance(session.output, LiveAvatarSocketOutput)
    assert session.stop is not None
    await session.stop()
