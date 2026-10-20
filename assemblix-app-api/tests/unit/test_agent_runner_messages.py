"""Unit tests for converting the OpenAI-style conversation into Pydantic AI messages."""

from pydantic_ai.messages import ModelRequest, ModelResponse

from assemblix_api.execution.agent_runner import CONTINUATION_PROMPT, to_pydantic_messages


def test_last_user_message_becomes_prompt() -> None:
    history, prompt = to_pydantic_messages(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "how are you?"},
        ]
    )

    assert prompt == "how are you?"
    assert [type(m) for m in history] == [ModelRequest, ModelResponse]


def test_history_ending_with_assistant_gets_closing_user_turn() -> None:
    history, prompt = to_pydantic_messages(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "previous agent reply"},
        ]
    )

    assert prompt == CONTINUATION_PROMPT
    assert isinstance(history[-1], ModelResponse)


def test_empty_conversation_keeps_empty_prompt() -> None:
    assert to_pydantic_messages([]) == ([], "")
