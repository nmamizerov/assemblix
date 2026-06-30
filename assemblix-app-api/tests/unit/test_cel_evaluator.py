"""Unit tests for the CEL evaluator (assemblix_api/core/cel_evaluator.py).

Covers expression evaluation across every context variable the engine exposes:

    state                 -> state.*
    project_state         -> project.*
    workflow (input_data) -> workflow.*
    node_input            -> input.*
    input_message         -> workflow.input_message  (derived from input_data["message"])
    input_parsed_message  -> input.parsed_message     (agent node output convention)

A single table-driven test evaluates each expression and checks the result.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from assemblix_api.core.cel_evaluator import CELEvaluator
from assemblix_api.schemas.execution import ExecutionContext
from assemblix_api.schemas.workflow import WorkflowDefinition

# ---------------------------------------------------------------------------
# Context data fed to every expression below.
# ---------------------------------------------------------------------------

STATE: dict[str, Any] = {
    "count": 5,
    "user": {"name": "Alice", "age": 30},
}

PROJECT_STATE: dict[str, Any] = {
    "tier": "pro",
    "credits": 100,
}

# input_data == the `workflow.*` namespace; "message" backs workflow.input_message.
INPUT_DATA: dict[str, Any] = {
    "message": "hello world",
    "locale": "ru",
}

# node_input == the `input.*` namespace; parsed_message backs input_parsed_message.
NODE_INPUT: dict[str, Any] = {
    "value": 21,
    "tags": ["vip", "beta", "early"],
    "numbers": [1, 2, 3],
    "message": "hello world",
    "parsed_message": {"intent": "greeting", "confidence": 0.95},
}

# ---------------------------------------------------------------------------
# List of CEL expressions with different functions + every parameter exercised.
# Each entry: (description, expression, expected_result)
# ---------------------------------------------------------------------------

CEL_CASES: list[tuple[str, str, Any]] = [
    # --- state.* ---
    ("state: field access", "state.count", 5),
    ("state: arithmetic", "state.count + 10", 15),
    ("state: range check (&&)", "state.count > 3 && state.count < 10", True),
    ("state: nested field", "state.user.name", "Alice"),
    # --- project_state -> project.* ---
    ("project_state: field access", "project.tier", "pro"),
    ("project_state: comparison", "project.credits >= 100", True),
    # --- workflow.* (input_data) ---
    ("workflow: field access", "workflow.locale", "ru"),
    # --- input_message -> workflow.input_message ---
    ("input_message: alias", "workflow.input_message", "hello world"),
    ("input_message: startsWith()", 'workflow.input_message.startsWith("hello")', True),
    ("input_message: contains()", 'workflow.input_message.contains("world")', True),
    ("input_message: endsWith()", 'workflow.input_message.endsWith("world")', True),
    ("input_message: matches() regex", 'workflow.input_message.matches("^hello.*")', True),
    ("input_message: size()", "size(workflow.input_message)", 11),
    ("input_message: string concat", '"Hi, " + workflow.input_message', "Hi, hello world"),
    # --- input.* (node_input) ---
    ("input: arithmetic", "input.value * 2", 42),
    ("input: list size()", "size(input.tags)", 3),
    ("input: in operator", '"vip" in input.tags', True),
    ("input: map() macro", "input.numbers.map(n, n * 2)", [2, 4, 6]),
    ("input: filter() macro", "input.numbers.filter(n, n > 1)", [2, 3]),
    ("input: exists() macro", "input.numbers.exists(n, n == 2)", True),
    ("input: all() macro", "input.numbers.all(n, n > 0)", True),
    # --- input_parsed_message -> input.parsed_message ---
    ("input_parsed_message: nested field", "input.parsed_message.intent", "greeting"),
    ("input_parsed_message: float compare", "input.parsed_message.confidence > 0.8", True),
    # --- functions / macros / cross-parameter ---
    ("ternary operator", 'state.count > 3 ? "big" : "small"', "big"),
    ("has() present", "has(state.count)", True),
    ("has() absent", "has(state.missing)", False),
    ("string() conversion", "string(state.count)", "5"),
    ("int() conversion", 'int("42") + 1', 43),
    ("cross-param: project + state", 'project.tier == "pro" && state.count == 5', True),
    ("cross-param: input vs workflow", "input.message == workflow.input_message", True),
]


def _make_context() -> ExecutionContext:
    """Build a minimal ExecutionContext carrying the state/project/input data.

    The evaluator only reads state, project_state, input_data, execution_id and
    chat_session_id, so the workflow snapshot can be an empty placeholder.
    """
    workflow = WorkflowDefinition(
        workflow_id=uuid4(),
        nodes=[],
        edges=[],
        state_schema=[],
        config={},
    )
    return ExecutionContext(
        execution_id=uuid4(),
        workflow_id=workflow.workflow_id,
        project_id=uuid4(),
        user_id=None,
        workflow=workflow,
        state=STATE,
        project_state=PROJECT_STATE,
        chat_session_id=None,
        client_session_id=None,
        input_data=INPUT_DATA,
        step_number=0,
        visited_nodes=[],
        node_execution_count={},
    )


def test_cel_evaluates_all_expressions() -> None:
    """Evaluate every expression in CEL_CASES and assert the result is correct."""
    # Arrange
    evaluator = CELEvaluator()
    context = _make_context()

    # Act + Assert (table-driven over all parameters and functions)
    for description, expression, expected in CEL_CASES:
        result = evaluator.evaluate(expression, context, NODE_INPUT)
        assert result == expected, (
            f"{description}: {expression!r} → {result!r}, expected {expected!r}"
        )
