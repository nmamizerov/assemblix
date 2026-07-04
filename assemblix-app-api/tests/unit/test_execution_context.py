"""Unit tests for ExecutionContext helpers (assemblix_api/schemas/execution.py).

Focus on with_chat_history: it both appends to the in-memory shared history that
downstream agents read AND records the last appended content, which finalization
persists as the assistant turn so the stored session history matches what agents
saw in-memory (respecting save_to_history / history_field).
"""

from __future__ import annotations

from tests.unit.nodes._helpers import make_context


def test_with_chat_history_appends_and_is_immutable() -> None:
    # Arrange
    context = make_context(chat_history=[{"role": "user", "content": "hi"}])

    # Act
    updated = context.with_chat_history([{"role": "assistant", "content": "answer"}])

    # Assert
    assert updated.chat_history == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "answer"},
    ]
    assert context.chat_history == [{"role": "user", "content": "hi"}]  # original untouched


def test_with_chat_history_records_last_message_for_persistence() -> None:
    # Arrange
    context = make_context(chat_history=[{"role": "user", "content": "hi"}])

    # Act — two successive appends (e.g. two agents saving to history).
    context = context.with_chat_history([{"role": "assistant", "content": "first"}])
    context = context.with_chat_history([{"role": "assistant", "content": "second"}])

    # Assert — the most recent appended content is what finalization will persist.
    assert context.last_history_message == "second"


def test_last_history_message_defaults_to_none() -> None:
    # Arrange / Act
    context = make_context()

    # Assert — no append yet → finalization falls back to the full final output.
    assert context.last_history_message is None
