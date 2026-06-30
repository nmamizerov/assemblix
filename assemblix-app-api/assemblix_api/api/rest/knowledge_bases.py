"""
Knowledge Base REST API endpoints
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_current_user,
    get_knowledge_base_service,
    get_project_service,
)
from assemblix_api.dto.requests.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    KnowledgeDocumentTextRequest,
)
from assemblix_api.dto.responses.knowledge_base import (
    KnowledgeBaseResponse,
    KnowledgeDocumentDetailResponse,
    KnowledgeDocumentResponse,
)
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Bases"])


@router.get("/", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    project_id: UUID = Query(..., description="Project ID"),
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    await project_service.verify_user_project_access(current_user, project_id)
    return await service.get_project_knowledge_bases(project_id)


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)
    return kb


@router.post("/", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    data: KnowledgeBaseCreateRequest,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    project = await project_service.verify_user_project_access(current_user, data.project_id)
    return await service.create_knowledge_base(project_id=project.id, data=data)


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: UUID,
    data: KnowledgeBaseUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)
    return await service.update_knowledge_base(kb_id=kb_id, data=data)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete a knowledge base together with all its documents."""
    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)
    await service.delete_knowledge_base(kb_id)


# ============================================
# Documents
# ============================================


@router.get("/{kb_id}/documents", response_model=list[KnowledgeDocumentResponse])
async def list_documents(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)
    return await service.get_kb_documents(kb_id)


@router.get("/{kb_id}/documents/{doc_id}", response_model=KnowledgeDocumentDetailResponse)
async def get_document(
    kb_id: UUID,
    doc_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)
    return await service.get_document(kb_id=kb_id, doc_id=doc_id)


@router.post(
    "/{kb_id}/documents/text",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_text_document(
    kb_id: UUID,
    data: KnowledgeDocumentTextRequest,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    max_bytes = get_settings().kb_max_upload_bytes
    if len(data.content.encode("utf-8")) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Текст слишком большой (максимум {max_bytes} байт)",
        )
    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)
    return await service.upload_document_text(kb_id=kb_id, data=data)


@router.post(
    "/{kb_id}/documents/pdf",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pdf_document(
    kb_id: UUID,
    file: UploadFile = File(..., description="PDF file to upload"),
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Upload a PDF document into a knowledge base.

    Accepts the file via multipart/form-data; the maximum size is bounded by
    the KB_MAX_UPLOAD_BYTES setting.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Файл должен быть в формате PDF",
        )

    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)

    max_bytes = get_settings().kb_max_upload_bytes
    # Read at most max_bytes + 1 so we can detect an oversized file without
    # pulling a huge file fully into memory.
    file_content = await file.read(max_bytes + 1)
    if len(file_content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF слишком большой (максимум {max_bytes} байт)",
        )
    return await service.upload_document_pdf(
        kb_id=kb_id,
        filename=file.filename,
        file_content=file_content,
    )


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: UUID,
    doc_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
    project_service: ProjectService = Depends(get_project_service),
):
    kb = await service.get_knowledge_base(kb_id)
    await project_service.verify_user_project_access(current_user, kb.project_id)
    await service.delete_document(kb_id=kb_id, doc_id=doc_id)
