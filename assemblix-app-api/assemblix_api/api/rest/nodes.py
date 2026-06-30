"""Node catalog endpoint. Drives the data-driven frontend node palette + forms."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from assemblix_api.core.node_loader import load_builtin_nodes, load_plugin_nodes
from assemblix_api.core.node_registry import NodeRegistry
from assemblix_api.dependencies import get_current_user
from assemblix_api.schemas.node_descriptor import NodeDescriptor

router = APIRouter(prefix="/nodes", tags=["nodes"])

# Idempotent: ensures the registry is populated even if a worker-only process
# imports this router before the app lifespan has run.
load_builtin_nodes()
load_plugin_nodes()


@router.get("", response_model=list[NodeDescriptor])
async def list_nodes(_user=Depends(get_current_user)) -> list[NodeDescriptor]:
    """Return all registered, user-visible node descriptors."""
    return NodeRegistry().get_descriptors()
