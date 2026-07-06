"""Pure graph scheduler for parallel (fork/join) workflow execution.

This is the traversal brain of the DAG engine, factored out of WorkflowExecutor the
same way GraphNavigator is: no asyncio, no DB, no node execution — just graph logic,
so it can be unit-tested exhaustively.

Model (borrowed from BPMN dead-path elimination + a token/wave scheme):

- A node **forks** when it has several outgoing edges: each edge delivers a token to
  its target. A plain node delivers a LIVE token on every outgoing edge; a routing
  node (CONDITION) delivers LIVE only on the selected branch and DEAD on the siblings.
- A node **joins** when it has several incoming edges: it fires only once it has a
  token (LIVE or DEAD) on every one of its forward incoming edges. It runs if at least
  one token is LIVE (its input is the merge of the LIVE predecessors' outputs); if all
  are DEAD it is itself dead and propagates DEAD downstream. This is what lets a
  CONDITION prune a branch that leads into a join without the join hanging forever
  (dead-path elimination).
- **Loops**: edges that close a cycle (back-edges, found by DFS from START) do not gate
  join readiness. A back-edge taken LIVE directly re-activates its target (one more
  loop iteration, bounded by the executor's per-node cycle cap). When a CONDITION takes
  a back-edge, its forward siblings are left PENDING (not killed) so a later iteration
  can still take them.

The executor drives it: seed with `start()`, run the returned nodes, then call
`complete()` for each finished node and run whatever it returns, until nothing is left.
Terminality, the cycle cap and node execution live in the executor; the scheduler only
decides *what runs next*.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from assemblix_api.schemas.workflow import Edge

# Token / branch liveness.
LIVE = "live"
DEAD = "dead"

# DFS colors for back-edge detection.
_WHITE = 0
_GRAY = 1
_BLACK = 2


@dataclass
class ReadyNode:
    """A node the executor should now run, with the input payload it receives.

    `input_data` is the merge of its LIVE predecessors' outputs (or the re-activating
    predecessor's output for a loop back-edge). START gets an empty dict — the executor
    substitutes the workflow input via the node's input_source hook.
    """

    node_id: str
    input_data: dict


@dataclass
class CompleteResult:
    """Outcome of completing one node.

    - `ready`: nodes unblocked by this completion (fork targets, a fired join, or a loop
      re-activation).
    - `live_out_count`: how many LIVE successor activations this node produced. The
      executor uses 0 on a non-terminal node to detect a dead-end (NoNextNodeError),
      matching the legacy single-path behaviour.
    """

    ready: list[ReadyNode]
    live_out_count: int


class DagScheduler:
    """Stateful, single-run scheduler over a workflow's node graph (pure/sync)."""

    def __init__(self, nodes: list[dict], edges: list[Edge], start_node_id: str):
        self._start = start_node_id
        node_ids = {n["id"] for n in nodes}

        # Keep only structurally valid edges: existing target, no self-loops — the same
        # invariants GraphNavigator enforces on the sequential path.
        self._edges: list[Edge] = [
            e for e in edges if e.target in node_ids and e.target != e.source
        ]

        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)
        for e in self._edges:
            self._out[e.source].append(e)
            self._in[e.target].append(e)

        self._back_edges: set[int] = self._compute_back_edges()
        # Forward (join-gating) incoming edges per node = incoming minus back-edges.
        self._forward_in: dict[str, list[Edge]] = {
            node_id: [e for e in in_edges if id(e) not in self._back_edges]
            for node_id, in_edges in self._in.items()
        }

        # Tokens accumulated on a node's forward-in edges since its last fire, keyed by
        # edge identity → LIVE/DEAD. Consumed when the node fires.
        self._tokens: dict[str, dict[int, str]] = defaultdict(dict)
        # Last output payload produced by each node (source of a successor's input).
        self._node_outputs: dict[str, dict] = {}
        # Nodes already resolved as dead — guards dead-path propagation against cycles.
        self._dead: set[str] = set()

    # --- public API -------------------------------------------------------------

    def start(self) -> list[ReadyNode]:
        """Seed the run: the START node is ready with no predecessor input."""
        return [ReadyNode(self._start, {})]

    def complete(
        self,
        node_id: str,
        output_data: dict,
        branch_index: int | None = None,
        is_terminal: bool = False,
    ) -> CompleteResult:
        """Record a finished node and return what becomes runnable because of it.

        Args:
            node_id: the node that just finished.
            output_data: its NodeOutput.data — fed to successors as their input.
            branch_index: for routing nodes (CONDITION) the selected outgoing handle
                index; None for a plain node (fan-out to all outgoing edges).
            is_terminal: END nodes have no successors; skip all edge labelling.
        """
        self._node_outputs[node_id] = output_data or {}

        out_edges = self._out.get(node_id, [])
        if is_terminal or not out_edges:
            return CompleteResult([], 0)

        ready: list[ReadyNode] = []
        live_out = 0

        if branch_index is not None:
            handle = f"source_{node_id}_{branch_index}"
            selected = [e for e in out_edges if e.source_handle == handle]
            selected_ids = {id(e) for e in selected}
            selected_is_back = any(id(e) in self._back_edges for e in selected)

            for e in selected:
                live_out += 1
                if id(e) in self._back_edges:
                    ready.append(ReadyNode(e.target, output_data or {}))
                else:
                    self._deliver(e, LIVE, ready)

            # Siblings the router did NOT pick. When the picked edge is a forward edge
            # they are dead-pathed (so a downstream join can complete); when the picked
            # edge loops back, leave forward siblings PENDING for a later iteration.
            for e in out_edges:
                if id(e) in selected_ids or id(e) in self._back_edges:
                    continue
                if selected_is_back:
                    continue
                self._deliver(e, DEAD, ready)
        else:
            # Plain node: every outgoing edge is LIVE (fork).
            for e in out_edges:
                live_out += 1
                if id(e) in self._back_edges:
                    ready.append(ReadyNode(e.target, output_data or {}))
                else:
                    self._deliver(e, LIVE, ready)

        return CompleteResult(ready, live_out)

    # --- internals --------------------------------------------------------------

    def _deliver(self, edge: Edge, status: str, ready: list[ReadyNode]) -> None:
        """Put a token on a forward edge and fire its target if now saturated."""
        target = edge.target
        self._tokens[target][id(edge)] = status
        self._maybe_fire(target, ready)

    def _maybe_fire(self, node_id: str, ready: list[ReadyNode]) -> None:
        forward_in = self._forward_in.get(node_id, [])
        if not forward_in:
            return
        tokens = self._tokens[node_id]
        # Wait until every forward incoming edge has delivered a token (join barrier).
        if len(tokens) < len(forward_in):
            return

        # Consume this wave's tokens so a later loop iteration starts fresh.
        self._tokens[node_id] = {}
        live_sources = [e for e in forward_in if tokens.get(id(e)) == LIVE]

        if live_sources:
            merged: dict = {}
            for e in live_sources:
                merged.update(self._node_outputs.get(e.source, {}))
            ready.append(ReadyNode(node_id, merged))
        else:
            # All incoming branches were pruned → this node is dead too.
            self._propagate_dead(node_id, ready)

    def _propagate_dead(self, node_id: str, ready: list[ReadyNode]) -> None:
        if node_id in self._dead:
            return
        self._dead.add(node_id)
        # Deadness flows down forward edges only (back-edges never gate a join), so the
        # recursion is over a DAG and terminates.
        for e in self._out.get(node_id, []):
            if id(e) in self._back_edges:
                continue
            self._deliver(e, DEAD, ready)

    def _compute_back_edges(self) -> set[int]:
        """Edges that close a cycle, via DFS from START (edge to a node on the stack).

        Iterative DFS to avoid recursion limits on large graphs. Nodes unreachable from
        START are ignored — they never execute anyway.
        """
        back: set[int] = set()
        color: dict[str, int] = defaultdict(lambda: _WHITE)
        # Stack of (node, iterator over its outgoing edges).
        stack: list[tuple[str, int]] = []

        color[self._start] = _GRAY
        stack.append((self._start, 0))
        while stack:
            node, idx = stack[-1]
            out = self._out.get(node, [])
            if idx < len(out):
                stack[-1] = (node, idx + 1)
                e = out[idx]
                target = e.target
                c = color[target]
                if c == _GRAY:
                    back.add(id(e))
                elif c == _WHITE:
                    color[target] = _GRAY
                    stack.append((target, 0))
            else:
                color[node] = _BLACK
                stack.pop()
        return back
