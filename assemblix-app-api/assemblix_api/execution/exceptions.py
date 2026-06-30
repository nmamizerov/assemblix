# /execution/exceptions.py


class ExecutionError(Exception):
    """Base exception for execution errors"""

    pass


class NodeNotFoundError(ExecutionError):
    """Node not found in workflow"""

    pass


class NoStartNodeError(ExecutionError):
    """No START node in workflow"""

    pass


class MultipleStartNodesError(ExecutionError):
    """Multiple START nodes found"""

    pass


class NoNextNodeError(ExecutionError):
    """No next node found (graph end without END node)"""

    pass


class MaxStepsExceededError(ExecutionError):
    """Max steps limit reached"""

    pass


class NodeExecutionLimitError(ExecutionError):
    """Node executed too many times"""

    pass


class WorkflowTimeoutError(ExecutionError):
    """Global wall-clock execution budget exceeded"""

    pass


class AgentRunTimeoutError(ExecutionError):
    """A single agent node exceeded its per-node wall-clock budget.

    Bounds the whole Pydantic AI loop (many completions + tool calls). Treated as
    FATAL by the error taxonomy: retrying would re-run already-executed tools.
    """

    pass


class NodeExecutionError(ExecutionError):
    """Wrapper exception that carries node_id information"""

    def __init__(self, original_error: Exception, node_id: str):
        self.original_error = original_error
        self.node_id = node_id
        super().__init__(str(original_error))
