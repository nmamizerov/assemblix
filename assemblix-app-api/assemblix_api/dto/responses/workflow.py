from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas import Edge, Node, StateVariable


class WorkflowBaseResponse(DTOModel):
    id: UUID = Field(description="Unique identifier of the workflow")
    name: str = Field(description="Human-readable name of the workflow")
    description: str | None = Field(
        default=None,
        description="Optional text description explaining the workflow's purpose",
    )
    is_active: bool = Field(
        description="Whether the workflow is currently active and available for execution"
    )
    is_published: bool = Field(
        description="Whether this workflow has been published as a versioned snapshot"
    )
    is_template: bool = Field(
        description="Whether this workflow is a reusable template that can be cloned"
    )
    created_at: datetime = Field(description="Timestamp when the workflow was created")
    updated_at: datetime = Field(description="Timestamp when the workflow was last modified")
    # Publishing fields
    published_for_workflow_id: UUID | None = Field(
        default=None,
        description="ID of the parent draft workflow this version was published from",
    )
    version: int | None = Field(
        default=None,
        description="Sequential version number assigned when the workflow is published",
    )


class WorkflowVersionInfo(DTOModel):
    id: UUID = Field(description="Unique identifier of this published workflow version")
    version: int = Field(description="Sequential version number of this publication")
    created_at: datetime = Field(description="Timestamp when this version was published")
    is_active: bool = Field(
        description="Whether this version is the currently active published version"
    )


class WorkflowResponse(WorkflowBaseResponse):
    edges: list[Edge] = Field(description="List of directed edges connecting workflow nodes")
    nodes: list[Node] = Field(description="List of all nodes in the workflow graph")
    state: list[StateVariable] = Field(
        description="List of state variable definitions used by the workflow"
    )
    config: dict = Field(
        default_factory=dict,
        description="Workflow-level config object (e.g. the avatar persona under `config.avatar`)",
    )
    # Published versions (only for drafts)
    versions: list[WorkflowVersionInfo] = Field(
        default=[],
        description="Published version history; only populated for draft workflows",
    )
