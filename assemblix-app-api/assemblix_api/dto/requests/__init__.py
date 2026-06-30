"""
Request DTOs module
"""

from .api_key import CreateAPIKeyRequest
from .auth import LoginRequest, RegisterRequest
from .chat_session import ChatSessionFilters
from .client_session import ClientSessionFilters, UpdateClientSessionMetadataRequest
from .credentials import CredentialsCreateRequest, CredentialsUpdateRequest
from .execution import (
    ExecuteWorkflowRequest,
    ExecutionFilters,
)
from .knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    KnowledgeDocumentTextRequest,
)
from .organization import (
    AddMemberRequest,
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    SetCurrentOrganizationRequest,
)
from .project import ProjectCreateRequest, ProjectUpdateRequest
from .workflow import WorkflowCreateRequest, WorkflowUpdateRequest

__all__ = [
    # Auth
    "LoginRequest",
    "RegisterRequest",
    # API Keys
    "CreateAPIKeyRequest",
    # Chat Sessions
    "ChatSessionFilters",
    # Client Sessions
    "ClientSessionFilters",
    "UpdateClientSessionMetadataRequest",
    # Credentials
    "CredentialsCreateRequest",
    "CredentialsUpdateRequest",
    # Organization
    "AddMemberRequest",
    "OrganizationCreateRequest",
    "OrganizationUpdateRequest",
    "SetCurrentOrganizationRequest",
    # Project
    "ProjectCreateRequest",
    "ProjectUpdateRequest",
    # Workflow
    "WorkflowCreateRequest",
    "WorkflowUpdateRequest",
    # Execution
    "ExecuteWorkflowRequest",
    "ExecutionFilters",
    # Knowledge Base
    "KnowledgeBaseCreateRequest",
    "KnowledgeBaseUpdateRequest",
    "KnowledgeDocumentTextRequest",
]
