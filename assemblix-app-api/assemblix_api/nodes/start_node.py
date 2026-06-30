# /nodes/start_node.py

from assemblix_api.core.node_registry import register_node
from assemblix_api.enums import NodeType
from assemblix_api.schemas.execution import NodeInput, NodeOutput
from assemblix_api.schemas.node import BaseNode


@register_node(NodeType.START)
class StartNode(BaseNode):
    """Start node - entry point of workflow.

    Reads from workflow_input (not from the previous node's output).
    """

    # Capability hook: START always reads from the workflow's initial input_data.
    input_source = "workflow_input"

    def __init__(self, node_config: dict):
        super().__init__(node_config)

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        return NodeOutput(data=node_input.context.input_data)
