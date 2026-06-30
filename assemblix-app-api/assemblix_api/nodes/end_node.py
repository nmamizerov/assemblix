# /nodes/end_node.py

from typing import Any

from assemblix_api.core.node_registry import register_node
from assemblix_api.enums import NodeType
from assemblix_api.schemas.execution import NodeInput, NodeOutput
from assemblix_api.schemas.node import BaseNode, EndNodeConfig


@register_node(NodeType.END)
class EndNode(BaseNode):
    """End node — end of workflow with flexible completion configuration.

    Setting is_terminal=True lets the executor exit the loop without a
    hardcoded NodeType.END check.
    """

    # Capability hook: reaching this node terminates the execution loop.
    is_terminal = True

    def __init__(self, node_config: dict):
        super().__init__(node_config)
        # Parse typed config for easier access
        self.typed_config = EndNodeConfig(**node_config.get("config", {}))

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        """
        Execute end node with flexible completion.

        Process:
        1. Determine output source based on output_mode
        2. Filter state and project_state
        3. Build metadata (is_error, error_message, is_session_end)
        4. Return NodeOutput with all data
        """
        context = node_input.context

        # 1. Determine output data
        output_data = await self._get_output_data(node_input)

        # 2. Filter states
        filtered_state = self._filter_state(
            context.state,
            self.typed_config.state_filter,
            self.typed_config.state_variables,
        )
        filtered_project_state = self._filter_state(
            context.project_state,
            self.typed_config.project_filter,
            self.typed_config.project_variables,
        )

        # 3. Build metadata
        metadata: dict[str, Any] = {
            "is_session_end": self.typed_config.is_session_end,
            "is_error": self.typed_config.is_error,
        }

        # Add filtered states to metadata (only for END node)
        if filtered_state is not None:
            metadata["filtered_state"] = filtered_state
        if filtered_project_state is not None:
            metadata["filtered_project_state"] = filtered_project_state

        # 4. Return NodeOutput
        return NodeOutput(
            data=output_data,
            metadata=metadata,
        )

    async def _get_output_data(self, node_input: NodeInput) -> dict:
        context = node_input.context
        output_mode = self.typed_config.output_mode

        # Default: None or "last_agent"
        if output_mode is None or output_mode == "last_agent":
            return await self._get_last_agent_output(context, node_input)

        # Specific agent node
        elif output_mode == "specific_agent":
            return await self._get_specific_agent_output(context, node_input)

        # Custom message
        elif output_mode == "custom":
            return self._get_custom_output(context, node_input)

        # Fallback (unreachable due to the Literal type)
        return node_input.data

    async def _get_last_agent_output(self, context, node_input: NodeInput) -> dict:
        if context.execution_tracer_service:
            last_agent_output = await context.execution_tracer_service.get_last_agent_output(
                context.execution_id
            )
            if last_agent_output:
                return last_agent_output

        # Fallback to input data
        return node_input.data

    async def _get_specific_agent_output(self, context, node_input: NodeInput) -> dict:
        if not self.typed_config.source_node_id:
            return node_input.data

        if context.execution_tracer_service:
            node_output = await context.execution_tracer_service.get_node_output(
                context.execution_id, self.typed_config.source_node_id
            )
            if node_output:
                return node_output

        # Fallback to input data
        return node_input.data

    def _get_custom_output(self, context, node_input: NodeInput) -> dict:
        if not self.typed_config.custom_message:
            return {"message": ""}

        # Evaluate CEL templates in custom message.
        # fallback_on_error=True: on evaluation error keep {{expr}} as-is.
        message = context.templates.render(
            self.typed_config.custom_message,
            context,
            node_input.data,
            fallback_on_error=True,
        )

        return {"message": message}

    @classmethod
    def descriptor(cls):
        """Catalog entry for the End node.

        Properties mirror EndNodeConfig: output mode, state filtering, and
        session/error flags.
        """
        from assemblix_api.schemas.node_descriptor import (
            NodeDescriptor,
            NodeDisplayCondition,
            NodeProperty,
            NodePropertyOption,
        )

        return NodeDescriptor(
            type="end",
            display_name="End",
            description="Terminates the workflow and returns the final output.",
            category="main",
            icon="CircleStop",
            color="node-tool",
            is_terminal=True,
            properties=[
                NodeProperty(
                    name="name",
                    display_name="Name",
                    type="string",
                    default="",
                    placeholder="e.g. Success",
                ),
                NodeProperty(
                    name="output_mode",
                    display_name="Output",
                    type="options",
                    default="last_agent",
                    options=[
                        NodePropertyOption(value="last_agent", label="Last agent"),
                        NodePropertyOption(value="specific_agent", label="Specific agent"),
                        NodePropertyOption(value="custom", label="Custom message"),
                    ],
                ),
                NodeProperty(
                    name="source_node_id",
                    display_name="Source node",
                    type="string",
                    show_when=NodeDisplayCondition(field="output_mode", values=["specific_agent"]),
                ),
                NodeProperty(
                    name="custom_message",
                    display_name="Message",
                    type="text",
                    show_when=NodeDisplayCondition(field="output_mode", values=["custom"]),
                ),
                NodeProperty(
                    name="state_filter",
                    display_name="State filter",
                    type="options",
                    default="all",
                    description="Which session-state variables to include in the completion payload.",
                    options=[
                        NodePropertyOption(value="all", label="All"),
                        NodePropertyOption(value="none", label="None"),
                        NodePropertyOption(value="selected", label="Selected"),
                    ],
                ),
                NodeProperty(
                    name="project_filter",
                    display_name="Project filter",
                    type="options",
                    default="all",
                    description="Which project-state variables to include in the completion payload.",
                    options=[
                        NodePropertyOption(value="all", label="All"),
                        NodePropertyOption(value="none", label="None"),
                        NodePropertyOption(value="selected", label="Selected"),
                    ],
                ),
                NodeProperty(
                    name="is_session_end",
                    display_name="End session",
                    type="boolean",
                    default=False,
                ),
                NodeProperty(
                    name="is_error",
                    display_name="Business error",
                    type="boolean",
                    default=False,
                    description="Mark this path as a business error (non-technical failure).",
                ),
            ],
        )

    def _filter_state(self, state: dict, filter_mode: str, variables: list[str]) -> dict | None:
        """Filter state by mode. Returns None for "all" (executor uses full state)."""
        if filter_mode == "all":
            return None

        elif filter_mode == "none":
            return {}

        elif filter_mode == "selected":
            return {key: state[key] for key in variables if key in state}

        # Default: all
        return None
