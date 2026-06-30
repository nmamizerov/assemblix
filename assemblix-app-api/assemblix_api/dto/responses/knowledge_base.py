from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class KnowledgeBaseResponse(DTOModel):
    id: UUID = Field(description="Unique identifier of the knowledge base")
    project_id: UUID = Field(description="ID of the project this knowledge base belongs to")
    name: str = Field(description="Display name of the knowledge base")
    description: str | None = Field(
        default=None,
        description="Optional description of the knowledge base purpose and contents",
    )
    document_count: int = Field(description="Number of documents stored in this knowledge base")
    total_characters: int = Field(
        description="Total character count across all documents in the knowledge base"
    )
    created_at: datetime = Field(description="Timestamp when the knowledge base was created")
    updated_at: datetime = Field(description="Timestamp when the knowledge base was last updated")


class KnowledgeDocumentResponse(DTOModel):
    id: UUID = Field(description="Unique identifier of the document")
    knowledge_base_id: UUID = Field(description="ID of the knowledge base this document belongs to")
    name: str = Field(description="Display name of the document")
    source_type: str = Field(description="Type of the document source (e.g. 'text', 'file', 'url')")
    character_count: int = Field(description="Number of characters in the document content")
    created_at: datetime = Field(description="Timestamp when the document was created")


class KnowledgeDocumentDetailResponse(KnowledgeDocumentResponse):
    content: str = Field(description="Full text content of the document")
