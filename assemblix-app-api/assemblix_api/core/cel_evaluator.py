# /core/cel_evaluator.py

import concurrent.futures
from collections import OrderedDict
from typing import Any

import celpy
import celpy.celtypes

from assemblix_api.core.settings import get_settings
from assemblix_api.schemas.execution import ExecutionContext

# CPU-DoS protection: CEL is not Turing-complete (no user loops/recursion), so the
# main attack vectors are expression length and the number of compiled programs kept
# in memory. Bound both.
_MAX_EXPRESSION_LENGTH = 10_000
_MAX_CACHE_SIZE = 10_000

# Best-effort timeout pool. A thread cannot be killed, so on timeout we return control
# to the caller (without blocking the event loop) while the background evaluation may
# still finish.
_eval_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="cel-eval")


class CELEvaluationError(Exception):
    """Raised when CEL expression evaluation fails"""

    pass


def cel_to_python(value: Any) -> Any:
    """
    Convert CEL types back to native Python types.

    CEL evaluation returns celpy types (IntType, StringType, etc.)
    which need to be converted to Python types for JSON serialization
    and database storage.

    Args:
        value: CEL type or Python value

    Returns:
        Native Python value
    """
    if value is None:
        return None

    # CEL primitive types
    if isinstance(value, celpy.celtypes.IntType):
        return int(value)
    if isinstance(value, celpy.celtypes.UintType):
        return int(value)
    if isinstance(value, celpy.celtypes.DoubleType):
        return float(value)
    if isinstance(value, celpy.celtypes.BoolType):
        return bool(value)
    if isinstance(value, celpy.celtypes.StringType):
        return str(value)
    if isinstance(value, celpy.celtypes.BytesType):
        return bytes(value)
    if isinstance(value, celpy.celtypes.NullType):
        return None

    # CEL collection types
    if isinstance(value, celpy.celtypes.ListType):
        return [cel_to_python(item) for item in value]
    if isinstance(value, celpy.celtypes.MapType):
        return {cel_to_python(k): cel_to_python(v) for k, v in value.items()}

    # CEL time types - convert to ISO string for JSON compatibility
    if isinstance(value, celpy.celtypes.TimestampType):
        return str(value)
    if isinstance(value, celpy.celtypes.DurationType):
        return str(value)

    # Already a Python type, return as-is
    return value


class CELEvaluator:
    """
    Wrapper over celpy for safe expression evaluation.
    Supports variables: state.*, input.*, workflow.*
    """

    def __init__(self):
        self.env = celpy.Environment()
        # OrderedDict used as a simple LRU: evict the oldest entry on overflow.
        self._expression_cache: OrderedDict[str, celpy.Runner] = OrderedDict()

    def evaluate(
        self,
        expression: str,
        context: ExecutionContext,
        node_input: dict[str, Any],
    ) -> Any:
        expression = str(expression)
        if len(expression) > _MAX_EXPRESSION_LENGTH:
            raise CELEvaluationError(
                f"CEL expression too long ({len(expression)} > {_MAX_EXPRESSION_LENGTH})"
            )
        runner = self._get_or_compile(expression)
        eval_context = self._build_context(context, node_input)

        timeout = get_settings().cel_evaluation_timeout_seconds
        try:
            # Run in a separate thread so a crafted expression cannot hang the event
            # loop indefinitely.
            future = _eval_executor.submit(runner.evaluate, eval_context)
            result = future.result(timeout=timeout)
            # Convert CEL types to Python types for JSON serialization
            return cel_to_python(result)
        except concurrent.futures.TimeoutError as e:
            raise CELEvaluationError(f"CEL expression evaluation timed out after {timeout}s") from e
        except Exception as e:
            raise CELEvaluationError(
                f"Failed to evaluate expression '{expression}': {str(e)}"
            ) from e

    def _get_or_compile(self, expression: str) -> celpy.Runner:
        cached = self._expression_cache.get(expression)
        if cached is not None:
            self._expression_cache.move_to_end(expression)
            return cached
        try:
            ast = self.env.compile(expression)
            runner = self.env.program(ast)
        except Exception as e:
            raise CELEvaluationError(
                f"Failed to compile expression '{expression}': {str(e)}"
            ) from e
        self._expression_cache[expression] = runner
        if len(self._expression_cache) > _MAX_CACHE_SIZE:
            self._expression_cache.popitem(last=False)  # evict oldest
        return self._expression_cache[expression]

    def _build_context(
        self,
        context: ExecutionContext,
        node_input: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build evaluation context with CEL types.

        CRITICAL: Must use celpy.json_to_cel() to convert Python dicts
        to CEL MapType, otherwise string comparison will fail!

        Available variables:
        - state.* - workflow-level state
        - project.* - project-level state (cross-workflow)
        - input.* - node input data
        - workflow.* - workflow input data
        - workflow.input_message - the original user message that started the
          workflow (stable alias, preserved across condition/set_variable/http_request)
        - client_id - client identifier (from input)
        - session_id - chat session identifier
        - execution_id - current execution identifier
        """
        # `workflow.input_message` is a derived field: it always reflects the run's
        # original message and overwrites any external `input_message` key in input_data.
        workflow_payload = {
            **context.input_data,
            "input_message": context.input_data.get("message", ""),
        }
        eval_context = {
            "state": celpy.json_to_cel(context.state),
            "project": celpy.json_to_cel(context.project_state),
            "input": celpy.json_to_cel(node_input),
            "workflow": celpy.json_to_cel(workflow_payload),
            "metadata": celpy.json_to_cel(
                {
                    "client_id": context.input_data.get("client_id"),
                    "session_id": (
                        str(context.chat_session_id) if context.chat_session_id else None
                    ),
                    "execution_id": str(context.execution_id),
                }
            ),
        }
        return eval_context

    def validate_syntax(self, expression: str) -> tuple[bool, str | None]:
        """
        Validate CEL expression syntax without evaluation.

        Returns:
            (is_valid, error_message)
        """
        try:
            self.env.compile(expression)
            return True, None
        except Exception as e:
            return False, str(e)

    def clear_cache(self) -> None:
        """Clear expression cache (useful for testing or memory management)"""
        self._expression_cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached expressions"""
        return len(self._expression_cache)
