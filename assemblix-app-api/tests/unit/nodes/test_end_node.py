"""Unit tests for the END node (assemblix_api/nodes/end_node.py).

END terminates the workflow. It:
- picks output data based on ``output_mode`` (default ``last_agent`` falls back to
  NodeInput.data when no execution tracer is wired);
- filters ``state`` / ``project_state`` per the filter mode (all → None, none → {},
  selected → subset), exposing the result under metadata keys;
- always records ``is_session_end`` and ``is_error`` in metadata;
- renders CEL ``{{...}}`` templates for the ``custom`` output mode.
"""

from __future__ import annotations

from assemblix_api.nodes.end_node import EndNode

from ._helpers import build_node, make_context, node_input


def _end(config: dict) -> EndNode:
    """Build an END node from its config dict."""
    return build_node(EndNode, "end", config)  # type: ignore[return-value]


async def test_end_is_terminal() -> None:
    """END declares the is_terminal capability hook so the executor stops the loop."""
    # Arrange
    node = _end({})

    # Act
    terminal = node.is_terminal

    # Assert
    assert terminal is True


async def test_end_default_mode_falls_back_to_input_data() -> None:
    """Default output_mode (last_agent) with no tracer returns NodeInput.data."""
    # Arrange
    context = make_context(state={"a": 1})
    node = _end({})
    incoming = {"message": "final answer"}

    # Act
    output = await node.execute(node_input(incoming, context))

    # Assert
    assert output.data == incoming


async def test_end_metadata_defaults() -> None:
    """Metadata carries is_session_end=False and is_error=False by default."""
    # Arrange
    context = make_context(state={})
    node = _end({})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.metadata is not None
    assert output.metadata["is_session_end"] is False
    assert output.metadata["is_error"] is False


async def test_end_error_and_session_flags_propagate() -> None:
    """is_error / is_session_end config flags are surfaced in metadata."""
    # Arrange
    context = make_context(state={})
    node = _end({"is_error": True, "is_session_end": True})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.metadata is not None
    assert output.metadata["is_error"] is True
    assert output.metadata["is_session_end"] is True


async def test_end_state_filter_all_omits_filtered_state() -> None:
    """state_filter='all' → _filter_state returns None → no filtered_state key."""
    # Arrange
    context = make_context(state={"a": 1, "b": 2})
    node = _end({"state_filter": "all"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.metadata is not None
    assert "filtered_state" not in output.metadata


async def test_end_state_filter_none_returns_empty() -> None:
    """state_filter='none' → filtered_state is an empty dict."""
    # Arrange
    context = make_context(state={"a": 1, "b": 2})
    node = _end({"state_filter": "none"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.metadata is not None
    assert output.metadata["filtered_state"] == {}


async def test_end_state_filter_selected_returns_subset() -> None:
    """state_filter='selected' keeps only the listed variables that exist."""
    # Arrange
    context = make_context(state={"a": 1, "b": 2, "c": 3})
    node = _end({"state_filter": "selected", "state_variables": ["a", "c", "missing"]})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.metadata is not None
    assert output.metadata["filtered_state"] == {"a": 1, "c": 3}


async def test_end_project_filter_selected_returns_subset() -> None:
    """project_filter='selected' keeps only the listed project variables."""
    # Arrange
    context = make_context(project_state={"tier": "pro", "credits": 100})
    node = _end({"project_filter": "selected", "project_variables": ["tier"]})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.metadata is not None
    assert output.metadata["filtered_project_state"] == {"tier": "pro"}


async def test_end_custom_mode_renders_cel_template() -> None:
    """output_mode='custom' renders {{...}} CEL templates in the message."""
    # Arrange
    context = make_context(state={"name": "Alice"})
    node = _end({"output_mode": "custom", "custom_message": "Hi {{state.name}}!"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.data == {"message": "Hi Alice!"}


async def test_end_custom_mode_empty_message() -> None:
    """output_mode='custom' with no message yields an empty message string."""
    # Arrange
    context = make_context(state={})
    node = _end({"output_mode": "custom"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.data == {"message": ""}
