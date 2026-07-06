"""Static graph checks that surface authoring mistakes the parallel engine cannot fix
at runtime. Pure functions over the node-graph JSON (no DB), used to drive editor
warnings and pre-run validation.

Two checks today:

- `detect_parallel_ends` — several END nodes reachable from a real parallel fork
  (an AND-split), so more than one END could fire in one run. The engine keeps only the
  first END that finishes; the others are silently ignored, which is almost never what
  the author meant. A CONDITION fan-out is fine (mutually exclusive) and never flagged.
- `detect_join_in_loop` — a join (node with 2+ incoming branches) that sits on a cycle.
  The v1 scheduler does not support synchronising a join across loop iterations, so this
  topology is flagged as unsupported.

Both mirror the engine's edge rules (skip edges to missing nodes and self-loops).
"""

from __future__ import annotations

from collections import defaultdict

from assemblix_api.enums import NodeType

_CONDITION = NodeType.CONDITION.value
_END = NodeType.END.value


def _valid_edges(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Edges with an existing, non-self target — the set the engine actually traverses."""
    node_ids = {n["id"] for n in nodes}
    return [
        e
        for e in edges
        if e.get("target") in node_ids
        and e.get("source") in node_ids
        and e.get("target") != e.get("source")
    ]


def _out_adjacency(edges: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        out[e["source"]].append(e["target"])
    return out


def _reachable_ends(start: str, out: dict[str, list[str]], end_ids: set[str]) -> set[str]:
    """Forward-reachable END node ids from `start` (cycle-safe)."""
    seen: set[str] = set()
    found: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if node in end_ids:
            found.add(node)
        stack.extend(out.get(node, []))
    return found


def detect_parallel_ends(nodes: list[dict], edges: list[dict]) -> list[str]:
    """END nodes that can fire in parallel (reached from an AND-split).

    An AND-split is any non-CONDITION node with 2+ distinct outgoing targets — all of
    its branches run concurrently. If two or more of those branches can each reach an
    END, and together they reach 2+ distinct END nodes, those ENDs race; only the first
    to finish is kept. Branches that reconverge to a single END (via a join) reach the
    same one END and are not flagged.

    Returns the sorted, de-duplicated node ids of the offending END nodes.
    """
    valid = _valid_edges(nodes, edges)
    node_type = {n["id"]: n.get("type") for n in nodes}
    end_ids = {nid for nid, t in node_type.items() if t == _END}
    if not end_ids:
        return []

    out = _out_adjacency(valid)

    # Distinct outgoing targets per source (dedupe multi-edges to the same node).
    branches: dict[str, list[str]] = defaultdict(list)
    for e in valid:
        if e["target"] not in branches[e["source"]]:
            branches[e["source"]].append(e["target"])

    flagged: set[str] = set()
    for source, targets in branches.items():
        if node_type.get(source) == _CONDITION or len(targets) < 2:
            continue  # not an AND-split
        per_branch_ends = [_reachable_ends(t, out, end_ids) for t in targets]
        contributing = [s for s in per_branch_ends if s]
        union: set[str] = set().union(*per_branch_ends) if per_branch_ends else set()
        # 2+ branches each reach an END, and they collectively reach 2+ distinct ENDs.
        if len(contributing) >= 2 and len(union) >= 2:
            flagged |= union

    return sorted(flagged)


def _nodes_on_cycle(out: dict[str, list[str]], node_ids: set[str]) -> set[str]:
    """Every node that lies on at least one directed cycle (Tarjan SCCs, iterative)."""
    index_counter = [0]
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    result: set[str] = set()

    for root in node_ids:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = lowlink[node] = index_counter[0]
                index_counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            successors = out.get(node, [])
            if pi < len(successors):
                work[-1] = (node, pi + 1)
                succ = successors[pi]
                if succ not in index:
                    work.append((succ, 0))
                elif on_stack.get(succ):
                    lowlink[node] = min(lowlink[node], index[succ])
            else:
                if lowlink[node] == index[node]:
                    # Pop one SCC; size>1 (or a self-referential SCC) means a cycle.
                    scc: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        scc.append(w)
                        if w == node:
                            break
                    if len(scc) > 1:
                        result.update(scc)
                work.pop()
                if work:
                    parent = work[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[node])
    return result


def detect_join_in_loop(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Join nodes (2+ incoming branches) that sit on a cycle — unsupported in v1.

    Returns the sorted node ids of such joins.
    """
    valid = _valid_edges(nodes, edges)
    node_ids = {n["id"] for n in nodes}

    incoming_sources: dict[str, set[str]] = defaultdict(set)
    for e in valid:
        incoming_sources[e["target"]].add(e["source"])
    join_nodes = {nid for nid, srcs in incoming_sources.items() if len(srcs) >= 2}
    if not join_nodes:
        return []

    on_cycle = _nodes_on_cycle(_out_adjacency(valid), node_ids)
    return sorted(join_nodes & on_cycle)
