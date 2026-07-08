from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas.node import WorkflowAvatarConfig

if TYPE_CHECKING:
    from assemblix_api.database.models import Workflow


class Edge(DTOModel):
    id: str
    source: str
    target: str
    source_handle: str | None = None
    target_handle: str | None = None


class StateVariable(DTOModel):
    name: str
    default_value: int | float | bool | str | dict | None = None
    type: Literal["number", "string", "boolean", "object"]


class WorkflowDefinition(DTOModel):
    """Immutable snapshot of a workflow definition passed to the execution engine."""

    workflow_id: UUID
    nodes: list[dict]
    edges: list[Edge]
    state_schema: list[StateVariable]
    config: dict

    @classmethod
    def from_workflow(cls, workflow: Workflow) -> WorkflowDefinition:
        return cls(
            workflow_id=workflow.id,
            nodes=workflow.nodes,
            edges=[Edge(**e) for e in workflow.edges],
            state_schema=[StateVariable(**s) for s in workflow.state],
            config=workflow.config or {},
        )


def parse_avatar_config(config: dict) -> WorkflowAvatarConfig | None:
    """Parse the workflow-global avatar persona from ``workflow.config``, or None."""
    raw = (config or {}).get("avatar")
    if not raw:
        return None
    return WorkflowAvatarConfig.model_validate(raw)
