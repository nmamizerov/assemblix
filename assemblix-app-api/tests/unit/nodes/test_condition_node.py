"""Unit tests for the CONDITION node (assemblix_api/nodes/condition_node.py).

CONDITION evaluates an ordered list of CEL expressions and routes to the first one
that is truthy. The chosen branch is exposed via ``condition_index`` in the output
data (and returned by ``get_branch_index``). When no condition matches it routes to
the else branch, whose index equals ``len(conditions)``. The node is a router, not a
transformer: it passes the incoming NodeInput.data through and adds bookkeeping fields.
"""

from __future__ import annotations

import pytest

from assemblix_api.nodes.condition_node import ConditionNode

from ._helpers import build_node, make_context, node_input


def _condition(expressions: list[dict]) -> ConditionNode:
    """Build a CONDITION node from a list of {expression, name} dicts."""
    return build_node(ConditionNode, "condition", {"conditions": expressions})  # type: ignore[return-value]


async def test_condition_first_match_wins() -> None:
    """The first truthy condition selects its index, even if a later one also matches."""
    # Arrange
    context = make_context(state={"count": 5})
    node = _condition(
        [
            {"expression": "state.count > 100", "name": "big"},
            {"expression": "state.count > 3", "name": "medium"},
            {"expression": "state.count > 0", "name": "small"},
        ]
    )

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert node.get_branch_index(output) == 1
    assert output.data["condition_index"] == 1
    assert output.data["condition_name"] == "medium"
    assert output.metadata is not None
    assert output.metadata["matched_condition"] == 1
    assert output.metadata["result"] is True


async def test_condition_else_branch_when_none_match() -> None:
    """No matching condition routes to the else branch (index == len(conditions))."""
    # Arrange
    context = make_context(state={"count": 5})
    node = _condition(
        [
            {"expression": "state.count > 100", "name": "big"},
            {"expression": "state.count > 50", "name": "medium"},
        ]
    )

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert node.get_branch_index(output) == 2
    assert output.data["condition_index"] == 2
    assert output.metadata is not None
    assert output.metadata["all_conditions_false"] is True


async def test_condition_passes_input_data_through() -> None:
    """The router forwards NodeInput.data, layering condition bookkeeping on top."""
    # Arrange
    context = make_context(state={"count": 5})
    node = _condition([{"expression": "true", "name": "always"}])
    incoming = {"message": "hi", "parsed_message": {"intent": "x"}}

    # Act
    output = await node.execute(node_input(incoming, context))

    # Assert
    assert output.data["message"] == "hi"
    assert output.data["parsed_message"] == {"intent": "x"}
    assert output.data["condition_index"] == 0


async def test_condition_evaluates_against_node_input_data() -> None:
    """Conditions can reference input.* (the previous node's output)."""
    # Arrange
    context = make_context(state={})
    node = _condition([{"expression": "input.score > 80", "name": "high"}])

    # Act
    output = await node.execute(node_input({"score": 95}, context))

    # Assert
    assert node.get_branch_index(output) == 0


async def test_condition_invalid_expression_raises_runtime_error() -> None:
    """A failing CEL evaluation is wrapped in a RuntimeError with the index/expression."""
    # Arrange
    context = make_context(state={})
    node = _condition([{"expression": "this is not valid cel ((", "name": "bad"}])

    # Act + Assert
    with pytest.raises(RuntimeError, match="Failed to evaluate condition 0"):
        await node.execute(node_input({}, context))
