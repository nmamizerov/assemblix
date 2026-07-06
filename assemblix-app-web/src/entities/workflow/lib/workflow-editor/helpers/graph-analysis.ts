import { NodeType } from "../../../model/types";

/**
 * Static graph checks that surface authoring mistakes the parallel execution engine
 * cannot fix at runtime. Ported 1:1 from the backend
 * (assemblix_api/execution/graph_analysis.py) so the editor warning matches what the
 * engine actually does:
 *
 * - `detectParallelEnds` — several END nodes reachable from a real parallel fork
 *   (an AND-split), so more than one END could fire in a single run. The engine keeps
 *   only the first END that finishes; the others are silently ignored. A CONDITION
 *   fan-out is mutually exclusive and never flagged.
 * - `detectJoinInLoop` — a join (node with 2+ incoming branches) sitting on a cycle,
 *   which the v1 scheduler does not support.
 *
 * `analyzeGraph` returns a map of node id → i18n message key for every flagged node.
 */

type GraphNode = { id: string; type?: string };
type GraphEdge = { source: string; target: string };

export const WARNING_KEYS = {
  parallelEnd: "workflow.node.warnings.parallelEndNodes",
  joinInLoop: "workflow.node.warnings.joinOnLoop",
} as const;

const validEdges = (nodes: GraphNode[], edges: GraphEdge[]): GraphEdge[] => {
  const ids = new Set(nodes.map((n) => n.id));
  return edges.filter(
    (e) => ids.has(e.target) && ids.has(e.source) && e.target !== e.source,
  );
};

const outAdjacency = (edges: GraphEdge[]): Map<string, string[]> => {
  const out = new Map<string, string[]>();
  for (const e of edges) {
    const list = out.get(e.source) ?? [];
    list.push(e.target);
    out.set(e.source, list);
  }
  return out;
};

// Forward-reachable END node ids from `start` (cycle-safe).
const reachableEnds = (
  start: string,
  out: Map<string, string[]>,
  endIds: Set<string>,
): Set<string> => {
  const seen = new Set<string>();
  const found = new Set<string>();
  const stack = [start];
  while (stack.length) {
    const node = stack.pop() as string;
    if (seen.has(node)) continue;
    seen.add(node);
    if (endIds.has(node)) found.add(node);
    stack.push(...(out.get(node) ?? []));
  }
  return found;
};

/** END node ids that can fire in parallel (reached from an AND-split). */
export const detectParallelEnds = (
  nodes: GraphNode[],
  edges: GraphEdge[],
): string[] => {
  const valid = validEdges(nodes, edges);
  const nodeType = new Map(nodes.map((n) => [n.id, n.type]));
  const endIds = new Set(
    nodes.filter((n) => n.type === NodeType.END).map((n) => n.id),
  );
  if (endIds.size === 0) return [];

  const out = outAdjacency(valid);

  // Distinct outgoing targets per source.
  const branches = new Map<string, string[]>();
  for (const e of valid) {
    const list = branches.get(e.source) ?? [];
    if (!list.includes(e.target)) list.push(e.target);
    branches.set(e.source, list);
  }

  const flagged = new Set<string>();
  for (const [source, targets] of branches) {
    if (nodeType.get(source) === NodeType.CONDITION || targets.length < 2) {
      continue; // not an AND-split
    }
    const perBranchEnds = targets.map((t) => reachableEnds(t, out, endIds));
    const contributing = perBranchEnds.filter((s) => s.size > 0);
    const union = new Set<string>();
    for (const s of perBranchEnds) for (const id of s) union.add(id);
    // 2+ branches each reach an END, and they collectively reach 2+ distinct ENDs.
    if (contributing.length >= 2 && union.size >= 2) {
      for (const id of union) flagged.add(id);
    }
  }
  return [...flagged].sort();
};

// Every node that lies on at least one directed cycle (Tarjan SCCs, iterative).
const nodesOnCycle = (
  out: Map<string, string[]>,
  nodeIds: string[],
): Set<string> => {
  let counter = 0;
  const index = new Map<string, number>();
  const lowlink = new Map<string, number>();
  const onStack = new Map<string, boolean>();
  const stack: string[] = [];
  const result = new Set<string>();

  for (const root of nodeIds) {
    if (index.has(root)) continue;
    const work: Array<[string, number]> = [[root, 0]];
    while (work.length) {
      const [node, pi] = work[work.length - 1];
      if (pi === 0) {
        index.set(node, counter);
        lowlink.set(node, counter);
        counter += 1;
        stack.push(node);
        onStack.set(node, true);
      }
      const successors = out.get(node) ?? [];
      if (pi < successors.length) {
        work[work.length - 1] = [node, pi + 1];
        const succ = successors[pi];
        if (!index.has(succ)) {
          work.push([succ, 0]);
        } else if (onStack.get(succ)) {
          lowlink.set(node, Math.min(lowlink.get(node)!, index.get(succ)!));
        }
      } else {
        if (lowlink.get(node) === index.get(node)) {
          const scc: string[] = [];
          for (;;) {
            const w = stack.pop() as string;
            onStack.set(w, false);
            scc.push(w);
            if (w === node) break;
          }
          if (scc.length > 1) for (const w of scc) result.add(w);
        }
        work.pop();
        if (work.length) {
          const parent = work[work.length - 1][0];
          lowlink.set(parent, Math.min(lowlink.get(parent)!, lowlink.get(node)!));
        }
      }
    }
  }
  return result;
};

/** Join nodes (2+ incoming branches) that sit on a cycle — unsupported in v1. */
export const detectJoinInLoop = (
  nodes: GraphNode[],
  edges: GraphEdge[],
): string[] => {
  const valid = validEdges(nodes, edges);

  const incomingSources = new Map<string, Set<string>>();
  for (const e of valid) {
    const set = incomingSources.get(e.target) ?? new Set<string>();
    set.add(e.source);
    incomingSources.set(e.target, set);
  }
  const joinNodes = new Set<string>();
  for (const [target, srcs] of incomingSources) {
    if (srcs.size >= 2) joinNodes.add(target);
  }
  if (joinNodes.size === 0) return [];

  const onCycle = nodesOnCycle(
    outAdjacency(valid),
    nodes.map((n) => n.id),
  );
  return [...joinNodes].filter((n) => onCycle.has(n)).sort();
};

/** Map of flagged node id → i18n warning key for the whole graph. */
export const analyzeGraph = (
  nodes: GraphNode[],
  edges: GraphEdge[],
): Record<string, string> => {
  const warnings: Record<string, string> = {};
  for (const id of detectParallelEnds(nodes, edges)) {
    warnings[id] = WARNING_KEYS.parallelEnd;
  }
  for (const id of detectJoinInLoop(nodes, edges)) {
    warnings[id] = WARNING_KEYS.joinInLoop;
  }
  return warnings;
};
