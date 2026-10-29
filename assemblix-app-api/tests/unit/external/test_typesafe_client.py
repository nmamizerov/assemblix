"""TypeSafe System One client — request shape, retries and error surfacing (respx)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from tenacity import wait_none

from assemblix_api.external.typesafe import client as ts_client
from assemblix_api.external.typesafe.client import TypeSafeError, system_one

URL = "https://api.typesafe.ai/v1/systemone"
QUESTIONS = {"billing": {"type": "noul", "instructions": "Is it about billing?"}}
OK_BODY = {
    "model": "jev-1.14.0",
    "answers": {"billing": {"type": "noul", "noul": 0.9}},
    "usage": {"input_tokens": 10, "output_tokens": 1},
}


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch) -> None:
    monkeypatch.setattr(ts_client, "_RETRY_WAIT", wait_none())


async def _call(**overrides):
    kwargs = {
        "api_key": "k",
        "model": "jev-latest",
        "state": "I was charged twice",
        "questions": QUESTIONS,
    }
    kwargs.update(overrides)
    return await system_one(**kwargs)


@respx.mock
async def test_sends_bearer_and_body() -> None:
    # Arrange
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    # Act
    result = await _call()
    # Assert
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer k"
    assert "TypeSafe-Danger-Zone-Long-Context" not in request.headers
    assert json.loads(request.content) == {
        "model": "jev-latest",
        "state": "I was charged twice",
        "questions": QUESTIONS,
    }
    assert result == OK_BODY


@respx.mock
async def test_long_context_header() -> None:
    # Arrange
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    # Act
    await _call(long_context=True)
    # Assert
    assert route.calls.last.request.headers["TypeSafe-Danger-Zone-Long-Context"] == "true"


@pytest.mark.parametrize("status", [429, 529])
@respx.mock
async def test_retries_transient_then_succeeds(status: int) -> None:
    # Arrange
    route = respx.post(URL).mock(
        side_effect=[httpx.Response(status), httpx.Response(200, json=OK_BODY)]
    )
    # Act
    result = await _call()
    # Assert
    assert result == OK_BODY
    assert route.call_count == 2


@respx.mock
async def test_400_not_retried() -> None:
    # Arrange
    route = respx.post(URL).mock(
        return_value=httpx.Response(400, json={"detail": "max_tokens_exceeded"})
    )
    # Act / Assert
    with pytest.raises(TypeSafeError) as exc:
        await _call()
    assert route.call_count == 1
    assert "400" in str(exc.value)
    assert "max_tokens_exceeded" in str(exc.value)


@respx.mock
async def test_422_detail_in_error() -> None:
    # Arrange
    detail = [{"loc": ["body", "state"], "msg": "Field required", "type": "missing"}]
    respx.post(URL).mock(return_value=httpx.Response(422, json={"detail": detail}))
    # Act / Assert
    with pytest.raises(TypeSafeError) as exc:
        await _call()
    assert "Field required" in str(exc.value)


@respx.mock
async def test_exhausted_retries_raises() -> None:
    # Arrange
    route = respx.post(URL).mock(return_value=httpx.Response(503, text="unavailable"))
    # Act / Assert
    with pytest.raises(TypeSafeError):
        await _call(max_retries=2)
    assert route.call_count == 3
