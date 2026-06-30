"""Declarative node spec consumed by GET /api/nodes and the data-driven frontend
renderer. Modeled after n8n's INodeTypeDescription / INodeProperties."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from assemblix_api.dto.base import DTOModel

PropertyType = Literal[
    "string",
    "text",
    "number",
    "boolean",
    "options",
    "json",
    "code",
    "credential",
    "knowledge_base",
    "key_value",
    "collection",
]


class NodePropertyOption(DTOModel):
    value: str
    label: str


class NodeDisplayCondition(DTOModel):
    """Show the owning property only when sibling `field` holds one of `values`."""

    field: str
    values: list[Any]


class NodeProperty(DTOModel):
    name: str
    display_name: str
    type: PropertyType
    default: Any = None
    required: bool = False
    placeholder: str | None = None
    description: str | None = None
    options: list[NodePropertyOption] = Field(default_factory=list)
    show_when: NodeDisplayCondition | None = None
    # For type="collection": the shape of each repeated item.
    fields: list[NodeProperty] = Field(default_factory=list)


class NodeDescriptor(DTOModel):
    type: str
    display_name: str
    description: str = ""
    category: str = "main"
    icon: str = "Box"  # Lucide icon name resolved client-side
    color: str = "node-default"
    sidebar_visible: bool = True
    is_terminal: bool = False
    branching: bool = False
    properties: list[NodeProperty] = Field(default_factory=list)


NodeProperty.model_rebuild()
