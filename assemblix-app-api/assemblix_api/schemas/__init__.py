"""Internal schemas used within the application; not exposed via the API directly."""

from assemblix_api.enums import AgentProvider

from .execution import ExecutionContext, ExecutionResult, NodeInput, NodeOutput
from .node import (
    AgentInstruction,
    AgentNode,
    AgentNodeConfig,
    BaseNode,
    Condition,
    ConditionNode,
    ConditionNodeConfig,
    EndNode,
    EndNodeConfig,
    GenericNode,
    Node,
    SetVariableNode,
    SetVariableNodeConfig,
    SmartMerge,
    StartNode,
    StartNodeConfig,
    StickerNode,
    StickerNodeConfig,
    UpdateVariable,
)
from .workflow import (
    Edge,
    StateVariable,
    WorkflowDefinition,
)

__all__ = [
    # Execution
    "ExecutionContext",
    "NodeInput",
    "NodeOutput",
    "ExecutionResult",
    # Workflow
    "WorkflowDefinition",
    "Node",
    "GenericNode",
    "BaseNode",
    "StartNode",
    "StartNodeConfig",
    "AgentNode",
    "AgentNodeConfig",
    "AgentProvider",
    "AgentInstruction",
    "ConditionNode",
    "ConditionNodeConfig",
    "Condition",
    "SetVariableNode",
    "SetVariableNodeConfig",
    "SmartMerge",
    "UpdateVariable",
    "EndNode",
    "EndNodeConfig",
    "StickerNode",
    "StickerNodeConfig",
    "Edge",
    "StateVariable",
]
