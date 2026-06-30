"""Smoke checks for the no-DB part of the harness (LLM mock seam).

These validate the scaffolding itself, not application behaviour — real test
cases per coverage zone are added on top of these fixtures.
"""

from __future__ import annotations

import pytest

from tests.fixtures.llm_responses import text_response, tool_call_response


async def test_mock_llm_patches_the_single_seam(mock_llm) -> None:
    """``mock_llm`` replaces ``litellm.acompletion`` and records calls."""
    from assemblix_api.external.llm import litellm_model

    mock_llm.set_response("hello from mock")
    resp = await litellm_model.litellm.acompletion(model="openai/gpt-4o", messages=[])

    assert resp.model_dump()["choices"][0]["message"]["content"] == "hello from mock"
    assert mock_llm.call_count == 1
    assert mock_llm.calls[0]["model"] == "openai/gpt-4o"


async def test_mock_llm_queue_responses(mock_llm) -> None:
    """Queued responses are returned in order (multi-turn / tool loops)."""
    from assemblix_api.external.llm import litellm_model

    mock_llm.queue_responses("first", "second")
    r1 = await litellm_model.litellm.acompletion(model="x", messages=[])
    r2 = await litellm_model.litellm.acompletion(model="x", messages=[])

    assert r1.model_dump()["choices"][0]["message"]["content"] == "first"
    assert r2.model_dump()["choices"][0]["message"]["content"] == "second"


@pytest.mark.parametrize(
    "builder, expected_finish",
    [
        (lambda: text_response("hi"), "stop"),
        (lambda: tool_call_response(name="web_search"), "tool_calls"),
    ],
)
def test_response_builders_shape(builder, expected_finish) -> None:
    """Canned builders produce a ChatCompletion-shaped payload."""
    payload = builder()
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["finish_reason"] == expected_finish
    assert "usage" in payload
