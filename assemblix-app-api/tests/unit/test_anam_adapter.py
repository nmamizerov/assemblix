import httpx
import pytest

from assemblix_api.external.avatar import anam


@pytest.mark.asyncio
async def test_mint_session_token_posts_persona_and_returns_token(monkeypatch):
    captured = {}

    async def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["json"] = httpx.Request(request.method, request.url, content=request.content).content
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
    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "a1", "name": "Cara"}]})

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(anam, "_client", lambda: httpx.AsyncClient(transport=transport))

    avatars = await anam.list_avatars("anam-key")

    assert [(a.id, a.name) for a in avatars] == [("a1", "Cara")]
