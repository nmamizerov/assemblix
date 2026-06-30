"""DELAY node — pauses the workflow for a bounded number of seconds, then passes
input through unchanged. Serves as the reference SDK example (see CONTRIBUTING_NODES.md)."""

import asyncio

from assemblix_api.core.node_registry import register_node
from assemblix_api.schemas.execution import NodeInput, NodeOutput
from assemblix_api.schemas.node import BaseNode
from assemblix_api.schemas.node_descriptor import NodeDescriptor, NodeProperty

_MAX_DELAY_SECONDS = 300.0


@register_node("delay")
class DelayNode(BaseNode):
    async def execute(self, node_input: NodeInput) -> NodeOutput:
        seconds = float(self.node_config.get("config", {}).get("seconds", 0) or 0)
        seconds = max(0.0, min(seconds, _MAX_DELAY_SECONDS))
        await asyncio.sleep(seconds)
        return NodeOutput(data=node_input.data)

    @classmethod
    def descriptor(cls) -> NodeDescriptor:
        return NodeDescriptor(
            type="delay",
            display_name="Delay",
            description="Pauses the workflow for a fixed number of seconds.",
            category="logic",
            icon="Clock",
            color="node-logic",
            properties=[
                NodeProperty(
                    name="seconds",
                    display_name="Seconds",
                    type="number",
                    default=1,
                    required=True,
                    description=f"0–{int(_MAX_DELAY_SECONDS)} seconds.",
                ),
            ],
        )
