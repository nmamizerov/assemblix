"""Unit tests for the litellm shim's stream=True path (_StreamShim)."""

from openai.types.chat import ChatCompletionChunk

from assemblix_api.external.llm.litellm_model import _Completions, _StreamShim


class _FakeLiteLLMChunk:
    """Mimics litellm ModelResponseStream: a pydantic-ish object with model_dump()."""

    def __init__(self, content: str):
        self._content = content

    def model_dump(self, warnings: bool = True) -> dict:
        return {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"content": self._content}, "finish_reason": None}],
        }


class _FakeLiteLLMStream:
    def __init__(self, contents):
        self._it = iter(contents)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return _FakeLiteLLMChunk(next(self._it))
        except StopIteration:
            raise StopAsyncIteration


async def test_stream_shim_yields_chatcompletionchunks_and_supports_context_manager(mocker) -> None:
    """create(stream=True) returns a _StreamShim yielding real ChatCompletionChunks."""
    # Arrange
    async def _fake_acompletion(**kwargs):
        assert kwargs.get("stream") is True
        return _FakeLiteLLMStream(["Hel", "lo"])

    mocker.patch(
        "assemblix_api.external.llm.litellm_model.litellm.acompletion",
        side_effect=_fake_acompletion,
    )
    completions = _Completions(defaults={}, env_overrides={}, api_key_env_var=None, api_key=None)

    # Act
    stream = await completions.create(model="openai/gpt-4o", messages=[], stream=True)
    collected = []
    async with stream as s:
        async for chunk in s:
            collected.append(chunk)
    await stream.close()

    # Assert
    assert isinstance(stream, _StreamShim)
    assert all(isinstance(c, ChatCompletionChunk) for c in collected)
    assert "".join(c.choices[0].delta.content or "" for c in collected) == "Hello"
