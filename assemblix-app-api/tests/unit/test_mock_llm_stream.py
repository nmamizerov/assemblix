"""Unit test for mock_llm streamed-chunk arming (set_stream)."""

import assemblix_api.external.llm.litellm_model as litellm_model


async def test_mock_llm_set_stream_yields_chunks(mock_llm) -> None:
    """set_stream arms a stream=True acompletion to yield the given text deltas in order."""
    # Arrange
    mock_llm.set_stream(["A", "B", "C"])

    # Act
    stream = await litellm_model.litellm.acompletion(
        model="openai/gpt-4o", messages=[], stream=True
    )
    contents = []
    async for chunk in stream:
        content = chunk.model_dump()["choices"][0]["delta"]["content"]
        if content is not None:
            contents.append(content)

    # Assert
    assert contents == ["A", "B", "C"]
    assert mock_llm.calls[0]["stream"] is True
