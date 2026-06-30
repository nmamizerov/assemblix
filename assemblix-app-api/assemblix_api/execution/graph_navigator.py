# /execution/graph_navigator.py


from assemblix_api.enums import NodeType
from assemblix_api.execution.exceptions import (
    MultipleStartNodesError,
    NoStartNodeError,
)
from assemblix_api.schemas.workflow import Edge


class GraphNavigator:
    """
    Handles graph traversal logic.
    Finds START node, navigates edges, handles conditions.
    """

    @staticmethod
    def find_start_node(nodes: list[dict]) -> str:
        """
        Find START node ID in workflow definition.

        Args:
            nodes: List of node configs from workflow

        Returns:
            ID of START node

        Raises:
            NoStartNodeError: If no START node found
            MultipleStartNodesError: If multiple START nodes found
        """
        start_nodes = [node for node in nodes if node.get("type") == NodeType.START.value]

        if len(start_nodes) == 0:
            raise NoStartNodeError("No START node found in workflow")

        if len(start_nodes) > 1:
            raise MultipleStartNodesError(
                f"Multiple START nodes found: {[n['id'] for n in start_nodes]}"
            )

        return start_nodes[0]["id"]

    @staticmethod
    def find_next_node(
        edges: list[Edge],
        nodes: list[dict],
        current_node_id: str,
        source_handle_index: int | None = None,
    ) -> str | None:
        """
        Find next node by traversing edges.

        Edges pointing to non-existent nodes are silently skipped so that
        stale references left in a saved workflow JSON do not crash execution.

        Args:
            edges: List of edges from workflow
            nodes: List of node configs from workflow (used to validate targets)
            current_node_id: ID of current node
            source_handle_index: Index for ConditionNode branching (0, 1, 2, etc.)
                                 If None, finds any edge from current node

        Returns:
            ID of next node, or None if not found

        Examples:
            # Regular node (single output)
            find_next_node(edges, nodes, "node_123")

            # ConditionNode with branching
            find_next_node(edges, nodes, "condition_456", 0)  # First condition branch
            find_next_node(edges, nodes, "condition_456", 1)  # Second condition branch
        """
        valid_node_ids = {node["id"] for node in nodes}

        # For ConditionNode: build source_handle and find matching edge
        if source_handle_index is not None:
            source_handle = f"source_{current_node_id}_{source_handle_index}"
            edge = next(
                (
                    e
                    for e in edges
                    if e.source == current_node_id
                    and e.source_handle == source_handle
                    and e.target in valid_node_ids
                ),
                None,
            )
            return edge.target if edge else None

        # For regular nodes: find first edge whose target actually exists
        edge = next(
            (e for e in edges if e.source == current_node_id and e.target in valid_node_ids),
            None,
        )
        return edge.target if edge else None
