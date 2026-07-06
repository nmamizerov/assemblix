"""Unit tests for GraphNavigator.find_next_node (assemblix_api/execution/graph_navigator.py).

Focus on the self-loop guard: a node must never be routed back to itself. An edge
whose target is the current node is skipped; the first real (non-self) edge is taken
instead, and when no such edge exists find_next_node returns None so the executor
fails fast with NoNextNodeError rather than spinning until the cycle cap trips.
"""

from __future__ import annotations

from assemblix_api.execution.graph_navigator import GraphNavigator
from assemblix_api.schemas.workflow import Edge


def _edge(source: str, target: str, handle: str | None = None) -> Edge:
    return Edge(
        id=f"{source}->{target}",
        source=source,
        target=target,
        source_handle=handle,
    )


def test_find_next_node_returns_normal_target() -> None:
    # Arrange
    nodes = [{"id": "A", "type": "agent"}, {"id": "B", "type": "end"}]
    edges = [_edge("A", "B")]

    # Act
    result = GraphNavigator.find_next_node(edges, nodes, "A")

    # Assert
    assert result == "B"


def test_find_next_node_skips_self_loop_and_takes_real_edge() -> None:
    # Arrange — the self-loop is listed FIRST, exactly like the prod bug.
    nodes = [{"id": "A", "type": "agent"}, {"id": "B", "type": "end"}]
    edges = [_edge("A", "A"), _edge("A", "B")]

    # Act
    result = GraphNavigator.find_next_node(edges, nodes, "A")

    # Assert — the self edge is ignored, execution moves forward to B.
    assert result == "B"


def test_find_next_node_returns_none_when_only_self_loop() -> None:
    # Arrange — the single outgoing edge points back at the node itself.
    nodes = [{"id": "A", "type": "agent"}]
    edges = [_edge("A", "A")]

    # Act
    result = GraphNavigator.find_next_node(edges, nodes, "A")

    # Assert — no valid successor → None (executor raises NoNextNodeError).
    assert result is None


def test_find_next_node_prod_repro_dead_edge_then_self_then_real() -> None:
    # Arrange — reproduces the prod graph exactly: the agent's outgoing edges were
    # ordered [-> deleted node, -> itself, -> real next]. Before the guard the self
    # edge won and the node ran until the cycle cap tripped.
    nodes = [{"id": "agent", "type": "agent"}, {"id": "cond", "type": "condition"}]
    edges = [
        _edge("agent", "deleted-node"),  # target missing → skipped (pre-existing)
        _edge("agent", "agent"),  # self-loop → skipped (new guard)
        _edge("agent", "cond"),  # first real successor
    ]

    # Act
    result = GraphNavigator.find_next_node(edges, nodes, "agent")

    # Assert
    assert result == "cond"


def test_find_next_node_excludes_self_loop_on_condition_branch() -> None:
    # Arrange — a branch edge that loops back to the condition node itself.
    nodes = [{"id": "C", "type": "condition"}]
    edges = [_edge("C", "C", handle="source_C_0")]

    # Act
    result = GraphNavigator.find_next_node(edges, nodes, "C", source_handle_index=0)

    # Assert
    assert result is None
