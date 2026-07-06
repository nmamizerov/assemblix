"""
REST API endpoints
"""

from fastapi import APIRouter

from assemblix_api.core.settings import get_settings

from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .billing import router as billing_router
from .chat_sessions import router as chat_sessions_router
from .client_sessions import router as client_sessions_router
from .config import router as config_router
from .credentials import router as credentials_router
from .executions import execution_detail_router
from .executions import router as executions_router
from .knowledge_bases import router as knowledge_bases_router
from .llm import router as llm_router
from .node_templates import router as node_templates_router
from .nodes import router as nodes_router
from .notification_channels import router as notification_channels_router
from .organizations import router as organizations_router
from .payments import router as payments_router
from .projects import router as projects_router
from .voice import router as voice_router
from .workflows import router as workflows_router

settings = get_settings()

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/api")
api_router.include_router(api_keys_router, prefix="/api")
api_router.include_router(billing_router, prefix="/api")
api_router.include_router(organizations_router, prefix="/api")
# Payments router is an Enterprise feature; mounted only when billing is enabled.
if settings.billing_enabled:
    api_router.include_router(payments_router, prefix="/api")
api_router.include_router(projects_router, prefix="/api")
api_router.include_router(workflows_router, prefix="/api")
api_router.include_router(credentials_router, prefix="/api")
api_router.include_router(node_templates_router, prefix="/api")
api_router.include_router(nodes_router, prefix="/api")
api_router.include_router(executions_router, prefix="/api")
api_router.include_router(execution_detail_router, prefix="/api")
api_router.include_router(chat_sessions_router, prefix="/api")
api_router.include_router(client_sessions_router, prefix="/api")
api_router.include_router(knowledge_bases_router, prefix="/api")
api_router.include_router(llm_router, prefix="/api")
api_router.include_router(voice_router, prefix="/api")
api_router.include_router(notification_channels_router, prefix="/api")
api_router.include_router(config_router, prefix="/api")
__all__ = ["api_router"]
