"""LLM mock harness (``mock_llm``) + in-memory Redis (``fake_redis``).

The single seam for all providers is ``litellm.acompletion``. Registered as a
plugin from ``tests/conftest.py`` (``pytest_plugins``).
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio


class LLMMock:
    """Controls the mocked ``litellm.acompletion`` for a test.

    All providers (OpenAI/Gemini/DeepSeek) funnel through this one
    call, so patching it exercises our parsing/billing/branching logic against a
    deterministic "expected" provider response.
    """

    def __init__(self, mocker: Any) -> None:
        self._mocker = mocker
        self.calls: list[dict[str, Any]] = []
        self.mock: Any = None
        # Default response so an un-configured agent call still succeeds.
        self._queue: list[dict[str, Any]] = []
        self._default = self._completion("OK")
        self._install()

    def _install(self) -> None:
        async def _acompletion(**kwargs: Any) -> Any:
            self.calls.append(kwargs)
            payload = self._queue.pop(0) if self._queue else self._default
            return _ModelResponse(payload)

        self.mock = self._mocker.patch(
            "assemblix_api.external.llm.litellm_model.litellm.acompletion",
            side_effect=_acompletion,
        )

    @staticmethod
    def _completion(
        content: str,
        *,
        model: str = "gpt-4o",
        tool_calls: list[dict[str, Any]] | None = None,
        prompt_tokens: int = 10,
        completion_tokens: int = 5,
    ) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": content}
        finish_reason = "stop"
        if tool_calls:
            message["tool_calls"] = tool_calls
            finish_reason = "tool_calls"
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    def set_response(self, content: str, **kwargs: Any) -> LLMMock:
        """Set the single response returned by the next (and every) call."""
        self._default = self._completion(content, **kwargs)
        self._queue.clear()
        return self

    def queue_responses(self, *responses: str) -> LLMMock:
        """Queue successive responses (e.g. for multi-turn / tool loops)."""
        self._queue = [self._completion(r) for r in responses]
        return self

    @property
    def call_count(self) -> int:
        return len(self.calls)


class _ModelResponse:
    """Mimics ``litellm.ModelResponse`` for the shim's ``.model_dump()`` call."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._payload


@pytest.fixture
def mock_llm(mocker: Any) -> LLMMock:
    """Patch the LLM seam; configure via ``mock_llm.set_response(...)``."""
    return LLMMock(mocker)


@pytest_asyncio.fixture
async def fake_redis() -> Any:
    """An in-memory async Redis stand-in (no real server)."""
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()
