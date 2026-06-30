# /nodes/condition_node.py

from assemblix_api.core.node_registry import register_node
from assemblix_api.enums import NodeType
from assemblix_api.schemas import BaseNode, ConditionNodeConfig, NodeInput, NodeOutput


@register_node(NodeType.CONDITION)
class ConditionNode(BaseNode):
    """
    Node for conditional branching (if-elseif-else logic).

    Evaluates conditions in order, returns index of first true condition.
    If all conditions are false, returns "else" (last edge).

    Edge naming convention:
    - source_handle="0" → first condition
    - source_handle="1" → second condition
    - source_handle="else" → default branch
    """

    def __init__(self, node_config: dict):
        super().__init__(node_config)
        # Parse and validate config
        self.typed_config = ConditionNodeConfig(**node_config["config"])

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        """
        Evaluate conditions and select next edge.

        Process:
        1. Iterate through conditions in order
        2. Evaluate each condition via CEL
        3. If condition is true → return its index as next_edge_id
        4. If all false → return "else"

        Returns:
            NodeOutput with next_edge_id set to condition index or "else"
        """
        cel_evaluator = node_input.context.cel_evaluator
        # A condition node cannot run without a CEL evaluator in its context.
        assert cel_evaluator is not None

        # Evaluate conditions in order
        for i, condition in enumerate(self.typed_config.conditions):
            try:
                result = cel_evaluator.evaluate(
                    condition.expression,
                    node_input.context,
                    node_input.data,
                )

                # A condition node is a router, not a transformer: pass node_input.data
                # through with service fields added on top. Otherwise message/parsed_message
                # from the previous node would be lost for the following steps.
                if result:
                    return NodeOutput(
                        data={
                            **node_input.data,
                            "condition_index": i,
                            "condition_name": condition.name,
                        },
                        metadata={
                            "matched_condition": i,
                            "condition_name": condition.name,
                            "expression": condition.expression,
                            "result": True,
                        },
                    )

            except Exception as e:
                # If evaluation fails, log and continue to next condition
                # (or could fail immediately - depends on desired behavior)
                raise RuntimeError(
                    f"Failed to evaluate condition {i} ('{condition.expression}'): {str(e)}"
                ) from e

        # No condition matched - go to else branch
        return NodeOutput(
            data={
                **node_input.data,
                "condition_index": len(self.typed_config.conditions),
            },
            metadata={
                "matched_condition": len(self.typed_config.conditions),
                "all_conditions_false": True,
            },
        )

    def get_branch_index(self, node_output: NodeOutput) -> int | None:
        """Return the condition_index stored in the output by execute().

        The GraphNavigator uses this to pick the correct outgoing edge
        (source_handle "0", "1", … or "else").
        """
        return node_output.data.get("condition_index")

    def validate_config(self) -> list[str]:
        """
        Validate node configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.typed_config.conditions:
            errors.append("At least one condition required")

        # Validate each condition syntax
        for i, condition in enumerate(self.typed_config.conditions):
            if not condition.expression:
                errors.append(f"Condition {i}: expression is required")
                continue
        return errors

    @classmethod
    def descriptor(cls):
        """Catalog entry for the Condition node.

        Properties mirror ConditionNodeConfig: a collection of named CEL expressions.
        """
        from assemblix_api.schemas.node_descriptor import NodeDescriptor, NodeProperty

        return NodeDescriptor(
            type="condition",
            display_name="Condition",
            description="Branches the workflow on CEL expressions (if-elseif-else).",
            category="logic",
            icon="GitFork",
            color="node-logic",
            branching=True,
            properties=[
                NodeProperty(
                    name="conditions",
                    display_name="Conditions",
                    type="collection",
                    description="Ordered list of named CEL conditions. "
                    "The first matching branch is taken; the last branch is the else.",
                    fields=[
                        NodeProperty(
                            name="name",
                            display_name="Name",
                            type="string",
                            placeholder="e.g. is_approved",
                        ),
                        NodeProperty(
                            name="expression",
                            display_name="Expression",
                            type="code",
                            required=True,
                            placeholder="e.g. input.score > 80",
                        ),
                    ],
                ),
            ],
        )
