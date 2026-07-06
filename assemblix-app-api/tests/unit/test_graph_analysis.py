"""Unit tests for static graph checks (assemblix_api/execution/graph_analysis.py).

detect_parallel_ends flags END nodes that could fire concurrently from a real
(AND-split) fork; detect_join_in_loop flags a join that sits on a cycle. Both are pure
graph functions over the node/edge JSON.
"""

from __future__ import annotations

from assemblix_api.execution.graph_analysis import detect_join_in_loop, detect_parallel_ends


def _node(node_id: str, node_type: str) -> dict:
    return {"id": node_id, "type": node_type}


def _edge(source: str, target: str, handle: str | None = None) -> dict:
    return {
        "id": f"{source}->{target}",
        "source": source,
        "target": target,
        "source_handle": handle,
    }


# --- detect_parallel_ends ---


def test_parallel_ends_flagged_for_and_split() -> None:
    # Arrange — START forks (AND-split) into two branches, each ending at its own END.
    nodes = [
        _node("start", "start"),
        _node("A", "agent"),
        _node("B", "agent"),
        _node("end1", "end"),
        _node("end2", "end"),
    ]
    edges = [
        _edge("start", "A"),
        _edge("start", "B"),
        _edge("A", "end1"),
        _edge("B", "end2"),
    ]

    # Act
    result = detect_parallel_ends(nodes, edges)

    # Assert — both ENDs can fire in parallel → both flagged.
    assert result == ["end1", "end2"]


def test_parallel_ends_ignores_condition_branching() -> None:
    # Arrange — a CONDITION fanning out to two ENDs is mutually exclusive, not parallel.
    nodes = [
        _node("start", "start"),
        _node("cond", "condition"),
        _node("end1", "end"),
        _node("end2", "end"),
    ]
    edges = [
        _edge("start", "cond"),
        _edge("cond", "end1", handle="source_cond_0"),
        _edge("cond", "end2", handle="source_cond_1"),
    ]

    # Act
    result = detect_parallel_ends(nodes, edges)

    # Assert — exactly one END ever runs → nothing flagged.
    assert result == []


def test_parallel_ends_ignores_branches_that_reconverge_to_one_end() -> None:
    # Arrange — an AND-split whose branches rejoin at J before a single shared END.
    nodes = [
        _node("start", "start"),
        _node("A", "agent"),
        _node("B", "agent"),
        _node("J", "agent"),
        _node("end", "end"),
    ]
    edges = [
        _edge("start", "A"),
        _edge("start", "B"),
        _edge("A", "J"),
        _edge("B", "J"),
        _edge("J", "end"),
    ]

    # Act
    result = detect_parallel_ends(nodes, edges)

    # Assert — only one END exists downstream of the join → not flagged.
    assert result == []


def test_parallel_ends_empty_without_ends() -> None:
    # Arrange
    nodes = [_node("start", "start"), _node("A", "agent")]
    edges = [_edge("start", "A")]

    # Act / Assert
    assert detect_parallel_ends(nodes, edges) == []


# --- detect_join_in_loop ---


def test_join_in_loop_flags_join_on_cycle() -> None:
    # Arrange — J joins A and B, and sits on a J → C → J cycle (unsupported in v1).
    nodes = [
        _node("start", "start"),
        _node("A", "agent"),
        _node("B", "agent"),
        _node("J", "agent"),
        _node("C", "condition"),
        _node("end", "end"),
    ]
    edges = [
        _edge("start", "A"),
        _edge("start", "B"),
        _edge("A", "J"),
        _edge("B", "J"),
        _edge("J", "C"),
        _edge("C", "J", handle="source_C_0"),  # loop back into the join
        _edge("C", "end", handle="source_C_1"),
    ]

    # Act
    result = detect_join_in_loop(nodes, edges)

    # Assert
    assert result == ["J"]


def test_join_in_loop_empty_for_acyclic_join() -> None:
    # Arrange — a plain fork/join with no cycle.
    nodes = [
        _node("start", "start"),
        _node("A", "agent"),
        _node("B", "agent"),
        _node("J", "agent"),
        _node("end", "end"),
    ]
    edges = [
        _edge("start", "A"),
        _edge("start", "B"),
        _edge("A", "J"),
        _edge("B", "J"),
        _edge("J", "end"),
    ]

    # Act / Assert
    assert detect_join_in_loop(nodes, edges) == []
