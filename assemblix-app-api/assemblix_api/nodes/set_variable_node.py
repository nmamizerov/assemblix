# /nodes/set_variable_node.py

import copy
import re

from assemblix_api.core.node_registry import register_node
from assemblix_api.enums import NodeType
from assemblix_api.schemas import (
    BaseNode,
    NodeInput,
    NodeOutput,
    SetVariableNodeConfig,
    UpdateVariable,
)

_SEGMENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@register_node(NodeType.SET_VARIABLE)
class SetVariableNode(BaseNode):
    """
    Node for updating workflow state variables.

    Supports:
    - Static values: {"variable_name": "status", "value": "active"}
    - CEL expressions: {"variable_name": "total", "value": "{{state.price * 1.2}}"}
    - Nested paths: {"variable_name": "state.user.profile.name", "value": "..."}
      writes only the leaf, preserving sibling fields of the parent object.
    """

    def __init__(self, node_config: dict):
        super().__init__(node_config)
        # Parse and validate config
        self.typed_config = SetVariableNodeConfig(**node_config["config"])

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        """
        Execute variable updates and smart merges.

        Process:
        1. Individual updates: parse variable name, evaluate value via CEL,
           write into nested path (auto-creating intermediate dicts).
        2. Smart merges: evaluate source CEL, apply operation to matching numeric keys.
        """
        state_updates: dict = {}
        project_updates: dict = {}
        updated_paths: list[str] = []

        # Phase 1: Individual updates
        for update in self.typed_config.updates:
            # Skip empty placeholder rows (UI seeds an empty update by default).
            if not (update.variable_name or "").strip():
                continue
            target, path = self._parse_variable_target(update.variable_name)
            value = self._resolve_value(update, node_input)

            if target == "project":
                accumulator = project_updates
                source_state = node_input.context.project_state
                path_label_prefix = "project."
            else:
                accumulator = state_updates
                source_state = node_input.context.state
                path_label_prefix = ""

            top = path[0]
            if len(path) == 1:
                accumulator[top] = value
            else:
                full_path = path_label_prefix + ".".join(path)
                if top in accumulator:
                    container = accumulator[top]
                else:
                    existing_top = source_state.get(top)
                    container = copy.deepcopy(existing_top) if existing_top is not None else {}
                if not isinstance(container, dict):
                    raise ValueError(
                        f"Cannot set '{full_path}': intermediate '{path_label_prefix}{top}' "
                        f"is {type(container).__name__}, expected dict."
                    )
                self._set_nested(container, path[1:], value, full_path, top)
                accumulator[top] = container

            updated_paths.append(path_label_prefix + ".".join(path))

        # Phase 2: Smart merges
        for merge in self.typed_config.merges:
            if merge.target == "project":
                full_target = {**node_input.context.project_state, **project_updates}
            else:
                full_target = {**node_input.context.state, **state_updates}

            # Resolve target: specific key or whole state
            if merge.target_key:
                target_dict = full_target.get(merge.target_key, {})
                if not isinstance(target_dict, dict):
                    raise ValueError(
                        f"Smart merge target_key '{merge.target_key}' must point to a dict, got {type(target_dict).__name__}"
                    )
            else:
                target_dict = full_target

            source_data = self._resolve_source(merge.source, node_input)
            if not isinstance(source_data, dict):
                raise ValueError(
                    f"Smart merge source must be a dict, got {type(source_data).__name__}"
                )

            merge_result = self._compute_merge(source_data, target_dict, merge.operation)

            # Write back: if target_key, nest result under that key
            if merge.target_key:
                nested = {**target_dict, **merge_result}
                final_updates = {merge.target_key: nested}
            else:
                final_updates = merge_result

            if merge.target == "project":
                project_updates.update(final_updates)
            else:
                state_updates.update(final_updates)

            updated_paths.extend(merge_result.keys())

        return NodeOutput(
            data=node_input.data,
            state_updates=state_updates if state_updates else None,
            project_updates=project_updates if project_updates else None,
            metadata={"updated_variables": updated_paths},
        )

    def _parse_variable_target(self, variable_name: str) -> tuple[str, list[str]]:
        """
        Parse variable name into (target, path).

        Examples:
            "state.counter" -> ("state", ["counter"])
            "state.user.profile.name" -> ("state", ["user", "profile", "name"])
            "project.user_name" -> ("project", ["user_name"])
            "counter" -> ("state", ["counter"])  # backwards compatibility

        Raises:
            ValueError: if any segment is empty or not a valid identifier.
        """
        if variable_name.startswith("project."):
            target = "project"
            remainder = variable_name[len("project.") :]
        elif variable_name.startswith("state."):
            target = "state"
            remainder = variable_name[len("state.") :]
        else:
            target = "state"
            remainder = variable_name

        segments = remainder.split(".")
        for segment in segments:
            if not _SEGMENT_RE.match(segment):
                raise ValueError(
                    f"Invalid variable name segment '{segment}' in '{variable_name}': "
                    "only [a-zA-Z_][a-zA-Z0-9_]* segments are supported (no array indexing)."
                )
        return target, segments

    def _set_nested(
        self,
        root: dict,
        path: list[str],
        value,
        full_path: str,
        top_key: str,
    ) -> None:
        """
        Walk `root` along `path[:-1]`, creating empty dicts when missing,
        and assign `value` at the leaf. Mutates `root` in place.

        Raises ValueError if any intermediate node exists but is not a dict.
        """
        node = root
        traversed = [top_key]
        for segment in path[:-1]:
            traversed.append(segment)
            existing = node.get(segment)
            if existing is None:
                new_dict: dict = {}
                node[segment] = new_dict
                node = new_dict
            elif isinstance(existing, dict):
                node = existing
            else:
                prefix = ".".join(traversed)
                raise ValueError(
                    f"Cannot set '{full_path}': intermediate '{prefix}' is "
                    f"{type(existing).__name__}, expected dict."
                )
        node[path[-1]] = value

    def _resolve_source(self, expression: str, node_input: NodeInput):
        """
        Resolve smart merge source via CEL expression.

        Args:
            expression: CEL expression (e.g. "input.parsed_message")
            node_input: Node input with context

        Returns:
            Resolved value (expected to be a dict)
        """
        cel_evaluator = node_input.context.cel_evaluator
        if not cel_evaluator:
            raise ValueError("CEL evaluator not found in context")
        return cel_evaluator.evaluate(expression, node_input.context, node_input.data)

    def _compute_merge(self, source: dict, target: dict, operation: str) -> dict:
        """
        Compute merge result for matching numeric keys.

        Only processes keys that exist in both source and target.
        Source value must be numeric (int or float, not bool).
        Target value can be numeric or None (None treated as 0 for add/subtract).

        Args:
            source: Source data from agent response
            target: Current target state
            operation: "add", "subtract", or "overwrite"

        Returns:
            Dict with computed updates (only changed keys)
        """
        result = {}
        for key, source_value in source.items():
            if key not in target:
                continue
            if not self._is_numeric(source_value):
                continue

            target_value = target[key]

            # null treated as 0 for arithmetic operations
            if target_value is None:
                if operation == "add":
                    result[key] = source_value
                elif operation == "subtract":
                    result[key] = -source_value
                elif operation == "overwrite":
                    result[key] = source_value
                continue

            if not self._is_numeric(target_value):
                continue

            if operation == "add":
                result[key] = target_value + source_value
            elif operation == "subtract":
                result[key] = target_value - source_value
            elif operation == "overwrite":
                result[key] = source_value
        return result

    @staticmethod
    def _is_numeric(value) -> bool:
        """Check if value is numeric (int or float, excluding bool)."""
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def _resolve_value(self, update: UpdateVariable, node_input: NodeInput):
        """
        Resolve update value - either static or CEL expression.

        Args:
            update: UpdateVariable with variable_name and value
            node_input: Node input with context

        Returns:
            Resolved value (any type)
        """
        value = update.value

        # Evaluate through CEL
        cel_evaluator = node_input.context.cel_evaluator
        if not cel_evaluator:
            raise ValueError("CEL evaluator not found in context")
        resolved_value = cel_evaluator.evaluate(
            str(value),
            node_input.context,
            node_input.data,
        )
        return resolved_value

    def validate_config(self) -> list[str]:
        """
        Validate node configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        for i, update in enumerate(self.typed_config.updates):
            if not update.variable_name:
                errors.append(f"Update {i}: variable_name is required")

        return errors

    @classmethod
    def descriptor(cls):
        """Catalog entry for the Set Variable node.

        Properties mirror SetVariableNodeConfig: a collection of individual variable
        updates and a collection of smart-merge rules.
        """
        from assemblix_api.schemas.node_descriptor import (
            NodeDescriptor,
            NodeProperty,
            NodePropertyOption,
        )

        return NodeDescriptor(
            type="set_variable",
            display_name="Set Variable",
            description="Updates workflow state variables using static values or CEL expressions.",
            category="data",
            icon="Database",
            color="node-data",
            properties=[
                NodeProperty(
                    name="updates",
                    display_name="Updates",
                    type="collection",
                    description="Individual variable assignments. "
                    "Use dot notation for nested paths (e.g. user.name) and "
                    "project. prefix for project-scoped variables.",
                    fields=[
                        NodeProperty(
                            name="variable_name",
                            display_name="Variable",
                            type="string",
                            required=True,
                            placeholder="e.g. counter or project.total",
                        ),
                        NodeProperty(
                            name="value",
                            display_name="Value",
                            type="string",
                            required=True,
                            placeholder="e.g. 42 or {{input.score}}",
                            description="Static value or CEL expression wrapped in {{ }}.",
                        ),
                    ],
                ),
                NodeProperty(
                    name="merges",
                    display_name="Smart merges",
                    type="collection",
                    description="Numeric merge operations applied to matching keys "
                    "between a source dict and the state.",
                    fields=[
                        NodeProperty(
                            name="source",
                            display_name="Source (CEL)",
                            type="code",
                            required=True,
                            placeholder="e.g. input.parsed_message",
                        ),
                        NodeProperty(
                            name="target",
                            display_name="Target scope",
                            type="options",
                            default="state",
                            options=[
                                NodePropertyOption(value="state", label="State"),
                                NodePropertyOption(value="project", label="Project"),
                            ],
                        ),
                        NodeProperty(
                            name="target_key",
                            display_name="Target key",
                            type="string",
                            placeholder="e.g. inventory (leave blank for whole state)",
                        ),
                        NodeProperty(
                            name="operation",
                            display_name="Operation",
                            type="options",
                            default="overwrite",
                            options=[
                                NodePropertyOption(value="overwrite", label="Overwrite"),
                                NodePropertyOption(value="add", label="Add"),
                                NodePropertyOption(value="subtract", label="Subtract"),
                            ],
                        ),
                    ],
                ),
            ],
        )
