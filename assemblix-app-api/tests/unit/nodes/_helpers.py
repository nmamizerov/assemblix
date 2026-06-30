"""Shared helpers for node unit tests.

Builds a minimal frozen ExecutionContext directly (no DB, no HTTP, no app) so each
node's ``execute(NodeInput)`` can be driven in isolation. The construction pattern
mirrors ``tests/unit/test_cel_evaluator.py::_make_context`` but is parameterized for
the per-node fields a given test needs (state, project_state, input_data, and a real
``CELEvaluator`` for nodes that evaluate CEL).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from assemblix_api.core.cel_evaluator import CELEvaluator
from assemblix_api.schemas.execution import ExecutionContext, NodeInput
from assemblix_api.schemas.node import BaseNode
from assemblix_api.schemas.workflow import WorkflowDefinition


def make_context(
    *,
    state: dict[str, Any] | None = None,
    project_state: dict[str, Any] | None = None,
    input_data: dict[str, Any] | None = None,
    with_cel: bool = True,
    chat_history: list[dict] | None = None,
    **extra: Any,
) -> ExecutionContext:
    """Build a minimal ExecutionContext for node unit tests.

    Args:
        state: workflow-level state (``state.*`` in CEL).
        project_state: project-level state (``project.*`` in CEL).
        input_data: workflow input (``workflow.*`` in CEL).
        with_cel: attach a real ``CELEvaluator`` (needed by condition / set_variable /
            http_request nodes and by ``{{...}}`` template rendering).
        chat_history: in-memory OpenAI-format chat history (used by the agent node).
        **extra: any additional ExecutionContext fields (e.g. credential_service,
            credential_resolver, organization_plan) for nodes that need them.

    Returns:
        A frozen ExecutionContext with an empty placeholder workflow snapshot.
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
        state=state if state is not None else {},
        project_state=project_state if project_state is not None else {},
        chat_session_id=None,
        client_session_id=None,
        input_data=input_data if input_data is not None else {},
        step_number=0,
        visited_nodes=[],
        node_execution_count={},
        cel_evaluator=CELEvaluator() if with_cel else None,
        chat_history=chat_history if chat_history is not None else [],
        **extra,
    )


def node_input(data: dict[str, Any], context: ExecutionContext) -> NodeInput:
    """Convenience wrapper for building a NodeInput."""
    return NodeInput(data=data, context=context)


def build_node(node_cls: type[BaseNode], node_type: str, config: dict[str, Any]) -> BaseNode:
    """Construct a node from a config dict the way the executor does.

    Nodes are built from ``{"id", "type", "position", "config": {...}}``.
    """
    return node_cls(
        {
            "id": f"{node_type}-1",
            "type": node_type,
            "position": {"x": 0, "y": 0},
            "config": config,
        }
    )
