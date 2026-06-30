from __future__ import annotations

from assemblix_api.enums import NodeType
from assemblix_api.schemas.node import BaseNode
from assemblix_api.schemas.node_descriptor import NodeDescriptor


class NodeNotFoundError(Exception):
    """Raised when node with given ID not found in workflow definition."""


class NodeTypeNotRegisteredError(Exception):
    """Raised when node type has no registered implementation."""


def _key(node_type: str | NodeType) -> str:
    """Coerce NodeType enum to its string value; pass plain strings through."""
    return node_type.value if isinstance(node_type, NodeType) else node_type


class NodeRegistry:
    """Factory for node instances, keyed by the node-type string.

    Built-in nodes register under their `NodeType` value (e.g. "agent"); plugin
    nodes register under any free-form string. The node_type column in execution_steps
    is a plain VARCHAR(100) — no Postgres enum constraint; any registered string
    persists without requiring a DB migration.
    """

    _instance: NodeRegistry | None = None
    _registry: dict[str, type[BaseNode]] = {}

    def __new__(cls) -> NodeRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, node_type: str | NodeType, node_class: type[BaseNode]) -> None:
        if not issubclass(node_class, BaseNode):
            raise TypeError(f"{node_class.__name__} must inherit from BaseNode")
        self._registry[_key(node_type)] = node_class

    def get_node(self, workflow_nodes: list[dict], node_id: str) -> BaseNode:
        node_config = next((n for n in workflow_nodes if n["id"] == node_id), None)
        if not node_config:
            raise NodeNotFoundError(f"Node '{node_id}' not found in workflow definition")
        node_type = node_config["type"]
        node_class = self._registry.get(node_type)
        if not node_class:
            raise NodeTypeNotRegisteredError(
                f"Node type '{node_type}' has no registered implementation. "
                f"Available types: {sorted(self._registry)}"
            )
        return node_class(node_config)

    def is_registered(self, node_type: str | NodeType) -> bool:
        return _key(node_type) in self._registry

    def registered_types(self) -> list[str]:
        """Return all registered node-type strings."""
        return list(self._registry)

    def get_descriptors(self) -> list[NodeDescriptor]:
        """Return NodeDescriptor for every registered node that exposes one."""
        out: list[NodeDescriptor] = []
        for cls in self._registry.values():
            desc = cls.descriptor()
            if desc is not None:
                out.append(desc)
        return out

    def clear(self) -> None:
        self._registry.clear()


registry = NodeRegistry()


def register_node(node_type: str | NodeType):
    """Decorator registering a node implementation under a type string.

    Accepts both a plain string (for plugin nodes) and a ``NodeType`` enum
    member (for built-in nodes). The enum value is stored under its ``.value``
    string so the registry stays string-keyed.
    """

    def decorator(node_class: type[BaseNode]):
        registry.register(node_type, node_class)
        return node_class

    return decorator
