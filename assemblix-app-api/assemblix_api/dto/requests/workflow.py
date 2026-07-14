from __future__ import annotations

from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas import Edge, Node, StateVariable


class WorkflowCreateRequest(DTOModel):
    project_id: UUID | None = Field(
        default=None,
        description="ID of the project this workflow belongs to. Optional when "
        "authenticated with a project-scoped API key — defaults to the key's project.",
    )
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Human-readable workflow name. If omitted, a default name is assigned",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional description explaining the workflow's purpose",
    )
    nodes: list[Node] = Field(
        default_factory=list,
        description="List of workflow nodes (start, end, agent, condition, etc.) forming the directed graph",
    )
    edges: list[Edge] = Field(
        default_factory=list,
        description="List of edges connecting nodes, defining the execution flow of the workflow graph",
    )
    state: list[StateVariable] = Field(
        default_factory=list,
        description="List of state variable definitions available to the workflow during execution",
    )
    config: dict = Field(
        default_factory=dict,
        description="Workflow-level config object (e.g. `config.avatar`)",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=500,
        description="Optional webhook URL that receives a POST callback when a workflow execution completes",
    )
    source: str = Field(
        default="assemblix",
        max_length=50,
        description="Product source: 'assemblix' for the main platform or 'chat' for the chat widget",
    )


class WorkflowUpdateRequest(DTOModel):
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Updated workflow name; pass null to leave unchanged",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Updated workflow description; pass null to leave unchanged",
    )
    nodes: list[Node] | None = Field(
        default=None,
        description="Full replacement list of workflow nodes; pass null to leave unchanged",
    )
    edges: list[Edge] | None = Field(
        default=None,
        description="Full replacement list of edges connecting nodes; pass null to leave unchanged",
    )
    state: list[StateVariable] | None = Field(
        default=None,
        description="Full replacement list of state variable definitions; pass null to leave unchanged",
    )
    config: dict | None = Field(
        default=None,
        description="Full replacement of the workflow-level config object (e.g. the "
        "avatar persona under `config.avatar`); pass null to leave unchanged",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=500,
        description="Updated webhook URL for execution completion callbacks; pass null to leave unchanged",
    )


class WorkflowMoveRequest(DTOModel):
    target_project_id: UUID = Field(
        ..., description="ID of the target project to move the workflow to"
    )
