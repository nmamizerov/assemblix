"""bitHuman cloud avatar: scoped token, room join request, error mapping, listing."""

import json

import httpx
import pytest
from fastapi import HTTPException

from assemblix_api.external.avatar import bithuman
from assemblix_api.external.avatar.errors import AvatarBusy, AvatarUnavailable
from assemblix_api.external.avatar.livekit_join import start_vendor_session

_ARGS = dict(
    api_key="master-secret",
    avatar_id="A78WKV4515",
    avatar_model="expression-2",
    livekit_url="wss://rtc.example.com",
    room_name="va-1",
)


def _mock(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(bithuman, "_client", lambda: httpx.AsyncClient(transport=transport))


def _ok_handler(calls: list[httpx.Request]):
    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/runtime-tokens/mint"):
            return httpx.Response(200, json={"scoped_token": "scoped-1", "expires_at": 1})
        return httpx.Response(200, json={"status": "success"})

    return handler


async def test_mints_a_scoped_token_then_starts_the_cloud_avatar(monkeypatch) -> None:
    # Arrange
    calls: list[httpx.Request] = []
    _mock(monkeypatch, _ok_handler(calls))
    token_attrs: list[dict] = []

    def make(extra: dict[str, str]) -> str:
        token_attrs.append(extra)
        return "lk-token"

    # Act
    await bithuman.start_livekit_session(make_livekit_token=make, **_ARGS)

    # Assert
    mint, start = calls
    assert str(mint.url) == "https://api.bithuman.ai/v1/runtime-tokens/mint"
    assert mint.headers["api-secret"] == "master-secret"
    assert json.loads(mint.content) == {
        "agent_code": "A78WKV4515",
        "scope": "livekit-cloud",
        "room_name": "va-1",
        "livekit_url": "wss://rtc.example.com",
    }
    assert str(start.url) == "https://auth.api.bithuman.ai/v1/runtime-tokens/request"
    assert start.headers["api-secret"] == "scoped-1"
    assert json.loads(start.content) == {
        "livekit_url": "wss://rtc.example.com",
        "livekit_token": "lk-token",
        "room_name": "va-1",
        "agent_id": "A78WKV4515",
        "model": "expression-2",
        "mode": "gpu",
    }
    assert token_attrs == [{"agent_id": "A78WKV4515", "api_secret": "scoped-1"}]


async def test_essence_models_run_in_cpu_mode(monkeypatch) -> None:
    calls: list[httpx.Request] = []
    _mock(monkeypatch, _ok_handler(calls))

    await bithuman.start_livekit_session(
        make_livekit_token=lambda extra: "t", **{**_ARGS, "avatar_model": "essence-2"}
    )

    assert json.loads(calls[1].content)["mode"] == "cpu"


def _fail_start(status: int, body: dict | str):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/runtime-tokens/mint"):
            return httpx.Response(200, json={"scoped_token": "scoped-1"})
        if isinstance(body, dict):
            return httpx.Response(status, json=body)
        return httpx.Response(status, text=body)

    return handler


async def test_concurrency_limit_is_busy(monkeypatch) -> None:
    _mock(
        monkeypatch,
        _fail_start(403, {"error": {"code": "CONCURRENCY_LIMIT_REACHED", "message": "limit"}}),
    )
    with pytest.raises(AvatarBusy):
        await bithuman.start_livekit_session(make_livekit_token=lambda e: "t", **_ARGS)


async def test_rate_limit_is_busy(monkeypatch) -> None:
    _mock(monkeypatch, _fail_start(429, {"error": {"code": "SESSION_LIMIT"}}))
    with pytest.raises(AvatarBusy):
        await bithuman.start_livekit_session(make_livekit_token=lambda e: "t", **_ARGS)


async def test_403_other_than_concurrency_is_unavailable(monkeypatch) -> None:
    _mock(monkeypatch, _fail_start(403, {"error": {"code": "RUNTIME_SUSPENDED"}}))
    with pytest.raises(AvatarUnavailable):
        await bithuman.start_livekit_session(make_livekit_token=lambda e: "t", **_ARGS)


async def test_out_of_credits_is_unavailable(monkeypatch) -> None:
    _mock(monkeypatch, _fail_start(402, {"error": {"code": "INSUFFICIENT_BALANCE"}}))
    with pytest.raises(AvatarUnavailable):
        await bithuman.start_livekit_session(make_livekit_token=lambda e: "t", **_ARGS)


async def test_failed_mint_is_unavailable(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "UNAUTHORIZED"}})

    _mock(monkeypatch, handler)
    with pytest.raises(AvatarUnavailable):
        await bithuman.start_livekit_session(make_livekit_token=lambda e: "t", **_ARGS)


async def test_mint_without_scoped_token_is_unavailable(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"expires_at": 1})

    _mock(monkeypatch, handler)
    with pytest.raises(AvatarUnavailable):
        await bithuman.start_livekit_session(make_livekit_token=lambda e: "t", **_ARGS)


async def test_transport_errors_are_unavailable(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    _mock(monkeypatch, handler)
    with pytest.raises(AvatarUnavailable):
        await bithuman.start_livekit_session(make_livekit_token=lambda e: "t", **_ARGS)


async def test_dispatch_routes_bithuman(monkeypatch) -> None:
    calls: list[httpx.Request] = []
    _mock(monkeypatch, _ok_handler(calls))

    await start_vendor_session(provider="bithuman", make_livekit_token=lambda e: "t", **_ARGS)

    assert len(calls) == 2


async def test_list_avatars_falls_back_to_code(monkeypatch) -> None:
    # Arrange
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["secret"] = request.headers["api-secret"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {"code": "A1", "name": "Wise Pup", "supported_models": ["essence-2"]},
                    {"code": "A2", "name": None, "supported_models": None},
                ],
            },
        )

    _mock(monkeypatch, handler)

    # Act
    avatars = await bithuman.list_avatars("master-secret")

    # Assert
    assert captured["url"] == "https://api.bithuman.ai/v1/agents?status=ready&limit=100"
    assert captured["secret"] == "master-secret"
    assert [(a.id, a.name, a.supported_models) for a in avatars] == [
        ("A1", "Wise Pup", ["essence-2"]),
        ("A2", "A2", []),
    ]


async def test_list_avatars_error_is_bad_gateway(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad secret")

    _mock(monkeypatch, handler)
    with pytest.raises(HTTPException) as exc:
        await bithuman.list_avatars("wrong")
    assert exc.value.status_code == 502


async def test_first_generation_models_use_the_start_api_spelling(monkeypatch) -> None:
    # Arrange
    calls: list[httpx.Request] = []
    _mock(monkeypatch, _ok_handler(calls))

    # Act
    await bithuman.start_livekit_session(
        make_livekit_token=lambda extra: "t", **{**_ARGS, "avatar_model": "essence-1"}
    )
    await bithuman.start_livekit_session(
        make_livekit_token=lambda extra: "t", **{**_ARGS, "avatar_model": "expression-1"}
    )

    # Assert
    first, second = json.loads(calls[1].content), json.loads(calls[3].content)
    assert (first["model"], first["mode"]) == ("essence", "cpu")
    assert (second["model"], second["mode"]) == ("expression", "gpu")
