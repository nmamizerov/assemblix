"""Unit tests for the SET_VARIABLE node (assemblix_api/nodes/set_variable_node.py).

SET_VARIABLE evaluates each update's value via CEL and writes it into ``state_updates``
or ``project_updates`` (the ``project.`` prefix routes to project scope). Nested dot
paths write only the leaf, preserving sibling fields. Smart merges apply numeric
``add``/``subtract``/``overwrite`` operations to keys present in both a CEL-resolved
source dict and the target state. NodeInput.data is passed through unchanged.
"""

from __future__ import annotations

import pytest

from assemblix_api.nodes.set_variable_node import SetVariableNode

from ._helpers import build_node, make_context, node_input


def _set_var(
    updates: list[dict] | None = None, merges: list[dict] | None = None
) -> SetVariableNode:
    """Build a SET_VARIABLE node from updates / merges config lists."""
    config = {"updates": updates or [], "merges": merges or []}
    return build_node(SetVariableNode, "set_variable", config)  # type: ignore[return-value]


async def test_static_value_via_cel() -> None:
    """A literal CEL value is evaluated and returned in state_updates."""
    # Arrange
    context = make_context(state={})
    node = _set_var(updates=[{"variable_name": "status", "value": '"active"'}])

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.state_updates == {"status": "active"}
    assert output.project_updates is None


async def test_cel_expression_referencing_state() -> None:
    """The value can be a CEL expression over current state."""
    # Arrange
    context = make_context(state={"price": 100})
    node = _set_var(updates=[{"variable_name": "total", "value": "state.price * 2"}])

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.state_updates == {"total": 200}


async def test_project_prefix_routes_to_project_updates() -> None:
    """A 'project.' prefixed variable lands in project_updates, not state_updates."""
    # Arrange
    context = make_context(project_state={})
    node = _set_var(updates=[{"variable_name": "project.tier", "value": '"pro"'}])

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.project_updates == {"tier": "pro"}
    assert output.state_updates is None


async def test_nested_path_preserves_siblings() -> None:
    """Writing state.user.name keeps existing sibling fields of user."""
    # Arrange
    context = make_context(state={"user": {"age": 30, "city": "NY"}})
    node = _set_var(updates=[{"variable_name": "state.user.name", "value": '"Alice"'}])

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.state_updates == {"user": {"age": 30, "city": "NY", "name": "Alice"}}


async def test_empty_update_row_is_skipped() -> None:
    """A blank variable_name placeholder row is ignored (no updates emitted)."""
    # Arrange
    context = make_context(state={})
    node = _set_var(updates=[{"variable_name": "  ", "value": "1"}])

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.state_updates is None
    assert output.project_updates is None


async def test_passes_input_data_through() -> None:
    """SET_VARIABLE forwards NodeInput.data unchanged."""
    # Arrange
    context = make_context(state={})
    node = _set_var(updates=[{"variable_name": "x", "value": "1"}])
    incoming = {"message": "hi"}

    # Act
    output = await node.execute(node_input(incoming, context))

    # Assert
    assert output.data == incoming
    assert output.metadata is not None
    assert "x" in output.metadata["updated_variables"]


async def test_smart_merge_add_numeric_keys() -> None:
    """Smart merge 'add' sums source values into matching numeric target keys."""
    # Arrange
    context = make_context(state={"gold": 10, "wood": 5})
    node = _set_var(
        merges=[
            {
                "source": "input.delta",
                "target": "state",
                "operation": "add",
            }
        ]
    )

    # Act
    output = await node.execute(node_input({"delta": {"gold": 3, "wood": 2}}, context))

    # Assert
    assert output.state_updates == {"gold": 13, "wood": 7}


async def test_smart_merge_into_target_key_nests_result() -> None:
    """Smart merge with target_key writes the merged dict under that key."""
    # Arrange
    context = make_context(state={"inventory": {"apples": 2}})
    node = _set_var(
        merges=[
            {
                "source": "input.parsed_message",
                "target": "state",
                "target_key": "inventory",
                "operation": "add",
            }
        ]
    )

    # Act
    output = await node.execute(node_input({"parsed_message": {"apples": 3}}, context))

    # Assert
    assert output.state_updates == {"inventory": {"apples": 5}}


async def test_smart_merge_non_dict_source_raises() -> None:
    """A smart-merge source that is not a dict raises ValueError."""
    # Arrange
    context = make_context(state={"x": 1})
    node = _set_var(merges=[{"source": '"not a dict"', "target": "state", "operation": "add"}])

    # Act + Assert
    with pytest.raises(ValueError, match="source must be a dict"):
        await node.execute(node_input({}, context))
