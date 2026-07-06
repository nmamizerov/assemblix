"""Unit tests for DagScheduler (assemblix_api/execution/dag_scheduler.py).

The scheduler is the pure traversal brain of the parallel engine: given completions it
decides what runs next. These tests drive it directly (no DB, no async) to cover
fork/join, dead-path elimination, condition→END exclusivity, and bounded loops.
"""

from __future__ import annotations

from assemblix_api.execution.dag_scheduler import DagScheduler, ReadyNode
from assemblix_api.schemas.workflow import Edge


def _edge(source: str, target: str, handle: str | None = None) -> Edge:
    return Edge(
        id=f"{source}->{target}:{handle}", source=source, target=target, source_handle=handle
    )


def _node(node_id: str, node_type: str = "agent") -> dict:
    return {"id": node_id, "type": node_type}


def _ids(ready: list[ReadyNode]) -> list[str]:
    return [r.node_id for r in ready]


# --- fork: one node → several parallel branches ---


def test_start_returns_start_node() -> None:
    # Arrange
    sched = DagScheduler([_node("start", "start")], [], "start")

    # Act
    ready = sched.start()

    # Assert
    assert _ids(ready) == ["start"]


def test_fork_activates_all_branches() -> None:
    # Arrange — start fans out to two independent branches.
    nodes = [_node("start", "start"), _node("A"), _node("B")]
    edges = [_edge("start", "A"), _edge("start", "B")]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()

    # Act
    result = sched.complete("start", {"x": 1})

    # Assert — both branches become runnable at once.
    assert _ids(result.ready) == ["A", "B"]
    assert result.live_out_count == 2


def test_fork_three_way() -> None:
    # Arrange
    nodes = [_node("start", "start"), _node("A"), _node("B"), _node("C")]
    edges = [_edge("start", "A"), _edge("start", "B"), _edge("start", "C")]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()

    # Act
    result = sched.complete("start", {})

    # Assert
    assert set(_ids(result.ready)) == {"A", "B", "C"}


# --- AND-join: a node with several incoming edges waits for all of them ---


def test_join_waits_for_all_branches_then_merges_inputs() -> None:
    # Arrange — start → A, start → B, both → J (join) → end.
    nodes = [_node("start", "start"), _node("A"), _node("B"), _node("J"), _node("end", "end")]
    edges = [
        _edge("start", "A"),
        _edge("start", "B"),
        _edge("A", "J"),
        _edge("B", "J"),
        _edge("J", "end"),
    ]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()
    sched.complete("start", {})

    # Act — A finishes first; J must NOT fire yet.
    after_a = sched.complete("A", {"a": 1})
    after_b = sched.complete("B", {"b": 2})

    # Assert — J fires only after B, with the merged inputs of both live branches.
    assert _ids(after_a.ready) == []
    assert _ids(after_b.ready) == ["J"]
    assert after_b.ready[0].input_data == {"a": 1, "b": 2}


# --- dead-path elimination: a pruned branch into a join must not hang it ---


def test_join_fires_when_one_incoming_branch_is_pruned() -> None:
    # Arrange — A reaches J live; a CONDITION C routes AWAY from J (its C→J edge dies).
    #   start → A → J ;  start → C ; C[0] → J ; C[1] → X ; J → end ; X → end_x
    nodes = [
        _node("start", "start"),
        _node("A"),
        _node("C", "condition"),
        _node("X"),
        _node("J"),
        _node("end", "end"),
        _node("end_x", "end"),
    ]
    edges = [
        _edge("start", "A"),
        _edge("start", "C"),
        _edge("A", "J"),
        _edge("C", "J", handle="source_C_0"),
        _edge("C", "X", handle="source_C_1"),
        _edge("J", "end"),
        _edge("X", "end_x"),
    ]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()
    sched.complete("start", {})
    sched.complete("A", {"a": 1})  # J now holds one LIVE token, still waiting on C

    # Act — C picks branch 1 (to X), so its edge into J is dead-pathed.
    result = sched.complete("C", {"c": 9}, branch_index=1)

    # Assert — X runs (live branch) AND J fires on A alone (dead C→J does not block it).
    assert set(_ids(result.ready)) == {"X", "J"}
    j = next(r for r in result.ready if r.node_id == "J")
    assert j.input_data == {"a": 1}  # only the LIVE predecessor contributes


def test_join_is_dead_when_all_incoming_branches_are_pruned() -> None:
    # Arrange — two conditions both route AWAY from J; J → K → end must all stay dead.
    nodes = [
        _node("start", "start"),
        _node("C1", "condition"),
        _node("C2", "condition"),
        _node("X1"),
        _node("X2"),
        _node("J"),
        _node("K"),
        _node("end", "end"),
    ]
    edges = [
        _edge("start", "C1"),
        _edge("start", "C2"),
        _edge("C1", "J", handle="source_C1_0"),
        _edge("C1", "X1", handle="source_C1_1"),
        _edge("C2", "J", handle="source_C2_0"),
        _edge("C2", "X2", handle="source_C2_1"),
        _edge("J", "K"),
        _edge("K", "end"),
    ]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()
    sched.complete("start", {})

    # Act — both conditions avoid J.
    r1 = sched.complete("C1", {}, branch_index=1)
    r2 = sched.complete("C2", {}, branch_index=1)

    # Assert — only the live X branches run; J/K/end never become ready (dead propagates).
    assert _ids(r1.ready) == ["X1"]
    assert _ids(r2.ready) == ["X2"]
    all_ready = _ids(r1.ready) + _ids(r2.ready)
    assert "J" not in all_ready
    assert "K" not in all_ready
    assert "end" not in all_ready


# --- condition → END exclusivity (this is NOT a parallel-END case) ---


def test_condition_runs_exactly_one_end_branch() -> None:
    # Arrange — start → C ; C[0] → end1 ; C[1] → end2.
    nodes = [
        _node("start", "start"),
        _node("C", "condition"),
        _node("end1", "end"),
        _node("end2", "end"),
    ]
    edges = [
        _edge("start", "C"),
        _edge("C", "end1", handle="source_C_0"),
        _edge("C", "end2", handle="source_C_1"),
    ]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()
    sched.complete("start", {})

    # Act — the first condition matches.
    result = sched.complete("C", {}, branch_index=0)

    # Assert — only end1 is scheduled; end2 is dead-pathed.
    assert _ids(result.ready) == ["end1"]


# --- bounded loops: back-edges re-activate, forward siblings survive iterations ---


def test_loop_backedge_reactivates_target_and_exit_reaches_end() -> None:
    # Arrange — start → A → C ; C[0] loops back to A ; C[1] → end.
    nodes = [
        _node("start", "start"),
        _node("A"),
        _node("C", "condition"),
        _node("end", "end"),
    ]
    edges = [
        _edge("start", "A"),
        _edge("A", "C"),
        _edge("C", "A", handle="source_C_0"),  # back-edge (loop)
        _edge("C", "end", handle="source_C_1"),  # forward exit
    ]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()
    sched.complete("start", {})
    sched.complete("A", {"i": 1})

    # Act — iteration 1: condition loops back to A.
    loop = sched.complete("C", {"i": 1}, branch_index=0)
    # iteration 2: A runs again, condition exits to end.
    sched.complete("A", {"i": 2})
    exit_ = sched.complete("C", {"i": 2}, branch_index=1)

    # Assert — the back-edge re-activates A; the forward exit still reaches end
    # (it was left PENDING, not killed, while the loop was taken).
    assert _ids(loop.ready) == ["A"]
    assert loop.live_out_count == 1
    assert _ids(exit_.ready) == ["end"]


def test_terminal_node_schedules_nothing() -> None:
    # Arrange
    nodes = [_node("start", "start"), _node("end", "end")]
    edges = [_edge("start", "end")]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()
    sched.complete("start", {})

    # Act — completing the END node yields no successors.
    result = sched.complete("end", {"message": "done"}, is_terminal=True)

    # Assert
    assert result.ready == []
    assert result.live_out_count == 0


def test_regular_node_dead_end_reports_zero_live_out() -> None:
    # Arrange — a non-terminal node whose only edge is a self-loop (skipped) → dead-end.
    nodes = [_node("start", "start"), _node("A")]
    edges = [_edge("start", "A"), _edge("A", "A")]
    sched = DagScheduler(nodes, edges, "start")
    sched.start()
    sched.complete("start", {})

    # Act
    result = sched.complete("A", {})

    # Assert — no successors and zero live-out so the executor can raise NoNextNodeError.
    assert result.ready == []
    assert result.live_out_count == 0
