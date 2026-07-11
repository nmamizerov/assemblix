import httpx
import pytest

from assemblix_api.external.avatar import anam


@pytest.mark.asyncio
async def test_mint_session_token_posts_persona_and_returns_token(monkeypatch):
    captured = {}

    async def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["json"] = httpx.Request(
            request.method, request.url, content=request.content
        ).content
        return httpx.Response(200, json={"sessionToken": "sess-123"})

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(anam, "_client", lambda: httpx.AsyncClient(transport=transport))

    token = await anam.mint_session_token(
        api_key="anam-key", persona_config={"name": "Cara", "llmId": "CUSTOMER_CLIENT_V1"}
    )

    assert token == "sess-123"
    assert captured["url"].endswith("/v1/auth/session-token")
    assert captured["auth"] == "Bearer anam-key"


@pytest.mark.asyncio
async def test_list_avatars_maps_items(monkeypatch):
    # Real anam /v1/avatars items carry displayName + optional variantName
    # (there is no single "name" field); the label combines them.
    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "a1", "displayName": "Cara", "variantName": "desk"},
                    {"id": "a2", "displayName": "Leo"},
                ]
            },
        )

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(anam, "_client", lambda: httpx.AsyncClient(transport=transport))

    avatars = await anam.list_avatars("anam-key")

    assert [(a.id, a.name) for a in avatars] == [("a1", "Cara (desk)"), ("a2", "Leo")]


@pytest.mark.asyncio
async def test_list_voices_maps_items_and_forwards_search(monkeypatch):
    # Voices come back under {data:[]}; name falls back to displayName/id. The
    # request forwards perPage=100 and the search term.
    captured = {}

    async def _handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={"data": [{"id": "v1", "displayName": "Aurora"}, {"id": "v2", "name": "Leo"}]},
        )

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(anam, "_client", lambda: httpx.AsyncClient(transport=transport))

    voices = await anam.list_voices("anam-key", search="aur")

    assert [(v.id, v.name) for v in voices] == [("v1", "Aurora"), ("v2", "Leo")]
    assert captured["params"]["perPage"] == "100"
    assert captured["params"]["search"] == "aur"
