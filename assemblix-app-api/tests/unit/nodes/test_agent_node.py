"""Unit tests for the AGENT node (assemblix_api/nodes/agent_node.py).

The agent node is the most wired node: it resolves a credential, builds messages
(instructions + KB + chat history), builds an in-process litellm model, and runs the
Pydantic AI agent loop. We keep this a real unit test by:

- mocking the single LLM seam (``litellm.acompletion``) via the ``mock_llm`` fixture;
- injecting a fake ``credential_resolver`` so no DB / real keys are touched
  (``_load_credential`` uses ``context.credential_resolver`` when present);
- providing the non-None ``credential_service`` and ``organization_plan`` that
  ``_load_credential`` asserts on.

The concurrency guard is a no-op without Redis (the test profile sets REDIS_URL="").

What is NOT covered here (would require much heavier wiring, out of scope for a unit
test): knowledge-base injection (needs a KnowledgeBaseService), multi-model fallback
behavior on transient errors, and tool/MCP loops. The happy path and JSON parsing are
covered, which exercises the node's own message-splitting and output-shaping logic.
"""

from __future__ import annotations

import json
import types

import pytest

from assemblix_api.enums import PlanTier
from assemblix_api.nodes.agent_node import AgentNode

from ._helpers import build_node, make_context, node_input


class _FakeResolver:
    """Stand-in for CredentialResolver: returns a fixed (api_key, is_system_key)."""

    def __init__(self, api_key: str = "sk-test", is_system_key: bool = True) -> None:
        self._api_key = api_key
        self._is_system_key = is_system_key

    async def resolve(self, **_kwargs: object) -> tuple[str, bool]:
        return self._api_key, self._is_system_key


def _agent_context(**extra):
    """Build a context with the agent-required fields wired (fake credential path)."""
    return make_context(
        credential_service=types.SimpleNamespace(),  # non-None; resolver bypasses it
        credential_resolver=_FakeResolver(),
        organization_plan=PlanTier.PRO,
        chat_history=[{"role": "user", "content": "Hello there"}],
        **extra,
    )


def _agent(config_overrides: dict | None = None) -> AgentNode:
    """Build an AGENT node with a minimal valid OpenAI config."""
    config = {
        "name": "Agent",
        "provider": "openai",
        "model": "gpt-4o",
        "instructions": [{"role": "system", "content": "You are helpful."}],
    }
    config.update(config_overrides or {})
    return build_node(AgentNode, "agent", config)  # type: ignore[return-value]


async def test_agent_happy_path_returns_message(mock_llm) -> None:
    """A successful run returns the LLM content in data['message'] and calls the LLM."""
    # Arrange
    mock_llm.set_response("Hi, how can I help?")
    context = _agent_context()
    node = _agent()

    # Act
    output = await node.execute(node_input({"message": "Hello there"}, context))

    # Assert
    assert output.data["message"] == "Hi, how can I help?"
    assert mock_llm.call_count == 1
    assert output.metadata is not None
    assert output.metadata["model"] == "gpt-4o"
    assert output.metadata["provider"] == "openai"
    assert output.metadata["used_system_key"] is True


async def test_agent_text_mode_does_not_parse_json(mock_llm) -> None:
    """Default text response_format leaves parsed_message as None."""
    # Arrange
    mock_llm.set_response("plain text answer")
    context = _agent_context()
    node = _agent()

    # Act
    output = await node.execute(node_input({"message": "Hello there"}, context))

    # Assert
    assert output.data["message"] == "plain text answer"
    assert output.data["parsed_message"] is None


async def test_agent_json_mode_parses_structured_output(mock_llm) -> None:
    """response_format=json_object parses the JSON content into parsed_message."""
    # Arrange
    mock_llm.set_response(json.dumps({"intent": "greeting", "confidence": 0.9}))
    context = _agent_context()
    node = _agent({"response_format": "json_object"})

    # Act
    output = await node.execute(node_input({"message": "Hello there"}, context))

    # Assert
    assert output.data["parsed_message"] == {"intent": "greeting", "confidence": 0.9}


async def test_agent_uses_configured_provider_and_model(mock_llm) -> None:
    """The configured model name reaches the litellm call."""
    # Arrange
    mock_llm.set_response("ok")
    context = _agent_context()
    node = _agent({"model": "gpt-4o-mini"})

    # Act
    await node.execute(node_input({"message": "Hello there"}, context))

    # Assert
    assert mock_llm.call_count == 1
    # litellm receives the provider-prefixed model id, e.g. "openai/gpt-4o-mini".
    assert "gpt-4o-mini" in mock_llm.calls[0]["model"]


async def test_agent_requires_credential_service() -> None:
    """Without a credential_service in the context, _load_credential asserts."""
    # Arrange
    context = make_context(
        credential_resolver=_FakeResolver(),
        organization_plan=PlanTier.PRO,
        chat_history=[{"role": "user", "content": "hi"}],
    )
    node = _agent()

    # Act + Assert
    with pytest.raises(AssertionError):
        await node.execute(node_input({"message": "hi"}, context))
