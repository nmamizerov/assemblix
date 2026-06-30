"""Canned LLM response payloads shaped like ``litellm.ModelResponse.model_dump()``.

The ``mock_llm`` fixture already builds these internally; these standalone
builders are for tests that want to assert on an exact payload, queue several, or
feed a tool-call / error shape explicitly.
"""

from __future__ import annotations

from typing import Any


def _envelope(message: dict[str, Any], *, model: str, finish_reason: str, usage: dict) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": usage,
    }


def usage(prompt_tokens: int = 10, completion_tokens: int = 5) -> dict[str, int]:
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def text_response(content: str, *, model: str = "gpt-4o", **usage_kw: int) -> dict[str, Any]:
    """A plain assistant text completion."""
    return _envelope(
        {"role": "assistant", "content": content},
        model=model,
        finish_reason="stop",
        usage=usage(**usage_kw),
    )


def json_response(content: str, *, model: str = "gpt-4o", **usage_kw: int) -> dict[str, Any]:
    """A completion whose content is a JSON string (for parse_json agents)."""
    return _envelope(
        {"role": "assistant", "content": content},
        model=model,
        finish_reason="stop",
        usage=usage(**usage_kw),
    )


def tool_call_response(
    *,
    name: str,
    arguments: str = "{}",
    call_id: str = "call_test",
    model: str = "gpt-4o",
    **usage_kw: int,
) -> dict[str, Any]:
    """A completion that requests a single tool call."""
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }
    return _envelope(message, model=model, finish_reason="tool_calls", usage=usage(**usage_kw))
