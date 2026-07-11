"""Unit tests for AgentRunner's streaming path (on_delta via event_stream_handler)."""

from assemblix_api.execution.agent_runner import AgentRunner
from assemblix_api.external.llm.litellm_model import build_litellm_model


async def test_run_streams_text_deltas_and_keeps_result_contract(mock_llm) -> None:
    """With on_delta, streamed deltas concatenate to the final content; contract unchanged (B5, B6)."""
    # Arrange
    mock_llm.set_stream(["Hel", "lo ", "world"])
    model = build_litellm_model("openai", "gpt-4o", "sk-test")
    seen: list[str] = []

    async def on_delta(text: str) -> None:
        seen.append(text)

    # Act
    result = await AgentRunner().run(
        model=model,
        provider="openai",
        model_name="gpt-4o",
        instructions=None,
        conversation=[{"role": "user", "content": "hi"}],
        on_delta=on_delta,
    )

    # Assert — B5: concatenation of deltas equals the final content
    assert "".join(seen) == "Hello world"
    assert result.content == "Hello world"
    # B6: usage/cost metadata still present (streaming does not drop the contract)
    assert "tokens_used" in result.metadata
    assert "cost" in result.metadata
    # The LLM call was made with stream=True
    assert mock_llm.calls[0]["stream"] is True


async def test_run_without_on_delta_is_non_streaming(mock_llm) -> None:
    """Without on_delta the buffered path is used (no stream=True) and still returns content."""
    # Arrange
    mock_llm.set_response("buffered answer")
    model = build_litellm_model("openai", "gpt-4o", "sk-test")

    # Act
    result = await AgentRunner().run(
        model=model,
        provider="openai",
        model_name="gpt-4o",
        instructions=None,
        conversation=[{"role": "user", "content": "hi"}],
    )

    # Assert
    assert result.content == "buffered answer"
    assert mock_llm.calls[0].get("stream") in (None, False)
