"""Unit tests for the START node (assemblix_api/nodes/start_node.py).

START is the workflow entry point: its ``execute`` returns ``context.input_data``
verbatim as the output data, regardless of the data passed in the NodeInput.
"""

from __future__ import annotations

from assemblix_api.nodes.start_node import StartNode

from ._helpers import build_node, make_context, node_input


async def test_start_returns_input_data() -> None:
    """START returns exactly context.input_data, ignoring NodeInput.data."""
    # Arrange
    workflow_input = {"message": "hello", "locale": "ru"}
    context = make_context(input_data=workflow_input, with_cel=False)
    node = build_node(StartNode, "start", {})

    # Act
    output = await node.execute(node_input({"ignored": True}, context))

    # Assert
    assert output.data == workflow_input
    assert output.state_updates is None
    assert output.project_updates is None
    assert output.metadata is None


async def test_start_input_source_is_workflow_input() -> None:
    """START declares its input_source capability hook as 'workflow_input'."""
    # Arrange
    node = build_node(StartNode, "start", {})

    # Act
    source = node.input_source

    # Assert
    assert source == "workflow_input"


async def test_start_empty_input_returns_empty_dict() -> None:
    """With no workflow input, START returns an empty dict (not None)."""
    # Arrange
    context = make_context(input_data={}, with_cel=False)
    node = build_node(StartNode, "start", {})

    # Act
    output = await node.execute(node_input({"x": 1}, context))

    # Assert
    assert output.data == {}
