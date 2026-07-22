import httpx
import pytest

from assemblix_api.external.voice import elevenlabs


@pytest.mark.asyncio
async def test_list_voices_hits_v2_and_requests_max_page_size(monkeypatch):
    # The v1 legacy endpoint returns a truncated default set; v2/voices paginates
    # (page_size max 100) and exposes the full library.
    captured = {}

    async def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url).split("?")[0]
        captured["params"] = dict(request.url.params)
        captured["api_key"] = request.headers.get("xi-api-key")
        return httpx.Response(
            200,
            json={
                "voices": [
                    {"voice_id": "v1", "name": "Aurora", "preview_url": "http://p/1"},
                    {"voice_id": "v2", "name": "Leo"},
                ],
                "has_more": False,
            },
        )

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(elevenlabs, "_client", lambda: httpx.AsyncClient(transport=transport))

    voices = await elevenlabs.list_voices("xi-key")

    assert [(v.id, v.name, v.preview_url) for v in voices] == [
        ("v1", "Aurora", "http://p/1"),
        ("v2", "Leo", None),
    ]
    assert captured["url"].endswith("/v2/voices")
    assert captured["params"]["page_size"] == "100"
    assert captured["api_key"] == "xi-key"


@pytest.mark.asyncio
async def test_list_voices_follows_pagination(monkeypatch):
    # has_more + next_page_token drive a follow-up request until the library is drained.
    pages = iter(
        [
            {
                "voices": [{"voice_id": "a", "name": "A"}],
                "has_more": True,
                "next_page_token": "tok-2",
            },
            {"voices": [{"voice_id": "b", "name": "B"}], "has_more": False},
        ]
    )
    seen_tokens = []

    async def _handler(request: httpx.Request) -> httpx.Response:
        seen_tokens.append(request.url.params.get("next_page_token"))
        return httpx.Response(200, json=next(pages))

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(elevenlabs, "_client", lambda: httpx.AsyncClient(transport=transport))

    voices = await elevenlabs.list_voices("xi-key")

    assert [v.id for v in voices] == ["a", "b"]
    assert seen_tokens == [None, "tok-2"]


@pytest.mark.asyncio
async def test_list_voices_forwards_search(monkeypatch):
    captured = {}

    async def _handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"voices": [], "has_more": False})

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(elevenlabs, "_client", lambda: httpx.AsyncClient(transport=transport))

    await elevenlabs.list_voices("xi-key", search="aur")

    assert captured["params"]["search"] == "aur"
