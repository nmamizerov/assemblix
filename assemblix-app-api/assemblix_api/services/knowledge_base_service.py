"""Knowledge Base Service - business logic for managing knowledge bases."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.knowledge_base import KnowledgeBase
from assemblix_api.database.models.knowledge_document import KnowledgeDocument
from assemblix_api.database.repositories.knowledge_base_repository import (
    KnowledgeBaseRepository,
)
from assemblix_api.database.repositories.knowledge_document_repository import (
    KnowledgeDocumentRepository,
)
from assemblix_api.dto.requests.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    KnowledgeDocumentTextRequest,
)
from assemblix_api.enums import KnowledgeDocumentSourceType

# Max combined KB text size for a single AgentNode call (~80 PDF pages)
MAX_COMBINED_CHARACTERS = 200_000


class KnowledgeBaseService:
    def __init__(
        self,
        kb_repository: KnowledgeBaseRepository,
        doc_repository: KnowledgeDocumentRepository,
    ):
        self._kb_repository = kb_repository
        self._doc_repository = doc_repository

    # ============================================
    # KnowledgeBase CRUD
    # ============================================

    async def create_knowledge_base(
        self,
        project_id: UUID,
        data: KnowledgeBaseCreateRequest,
    ) -> KnowledgeBase:
        return await self._kb_repository.create(
            project_id=project_id,
            name=data.name,
            description=data.description,
            document_count=0,
            total_characters=0,
        )

    async def get_knowledge_base(self, kb_id: UUID) -> KnowledgeBase:
        kb = await self._kb_repository.get_by_id(kb_id)
        if kb is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"База знаний с ID {kb_id} не найдена",
            )
        return kb

    async def get_project_knowledge_bases(self, project_id: UUID) -> Sequence[KnowledgeBase]:
        return await self._kb_repository.get_by_project_id(project_id)

    async def update_knowledge_base(
        self,
        kb_id: UUID,
        data: KnowledgeBaseUpdateRequest,
    ) -> KnowledgeBase:
        kb = await self.get_knowledge_base(kb_id)

        update_fields = {}
        if data.name is not None:
            update_fields["name"] = data.name
        if data.description is not None:
            update_fields["description"] = data.description

        if not update_fields:
            return kb

        return await self._kb_repository.update(kb, **update_fields)

    async def delete_knowledge_base(self, kb_id: UUID) -> None:
        kb = await self.get_knowledge_base(kb_id)
        await self._kb_repository.delete_instance(kb)

    # ============================================
    # Documents
    # ============================================

    async def upload_document_text(
        self,
        kb_id: UUID,
        data: KnowledgeDocumentTextRequest,
    ) -> KnowledgeDocument:
        """
        Upload a text document into a knowledge base.

        Raises:
            HTTPException 404: KB not found
            HTTPException 409: a document with the same content already exists
            HTTPException 422: adding the document would exceed the KB size limit
        """
        kb = await self.get_knowledge_base(kb_id)

        content = data.content.strip()

        # Check the size limit before persisting
        _check_size_limit(kb.total_characters, len(content))

        content_hash = _compute_hash(content)

        existing = await self._doc_repository.get_by_content_hash(kb_id, content_hash)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Документ с таким содержимым уже существует в этой базе знаний",
            )

        doc = await self._doc_repository.create(
            knowledge_base_id=kb_id,
            name=data.name,
            source_type=KnowledgeDocumentSourceType.TEXT.value,
            content=content,
            character_count=len(content),
            content_hash=content_hash,
        )

        await self._kb_repository.update(
            kb,
            document_count=kb.document_count + 1,
            total_characters=kb.total_characters + len(content),
        )

        return doc

    async def upload_document_pdf(
        self,
        kb_id: UUID,
        filename: str,
        file_content: bytes,
    ) -> KnowledgeDocument:
        """
        Upload a PDF document into a knowledge base.

        Extracts plain text from the PDF, then stores it as a document.

        Raises:
            HTTPException 404: KB not found
            HTTPException 409: a document with the same content already exists
            HTTPException 422: PDF invalid, contains no text, or would exceed the KB limit
        """
        from assemblix_api.utils.pdf_parser import extract_text_from_pdf

        kb = await self.get_knowledge_base(kb_id)

        settings = get_settings()

        # Extract PDF text in a separate thread with a timeout and page limit —
        # protects against DoS (malicious/huge/looping PDFs).
        try:
            content = await asyncio.wait_for(
                asyncio.to_thread(
                    extract_text_from_pdf,
                    file_content,
                    settings.kb_max_pdf_pages,
                ),
                timeout=settings.kb_pdf_parse_timeout_seconds,
            )
        except TimeoutError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Не удалось обработать PDF за отведённое время",
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(e),
            ) from e

        # Check the size limit before persisting
        _check_size_limit(kb.total_characters, len(content))

        content_hash = _compute_hash(content)

        existing = await self._doc_repository.get_by_content_hash(kb_id, content_hash)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Документ с таким содержимым уже существует в этой базе знаний",
            )

        doc = await self._doc_repository.create(
            knowledge_base_id=kb_id,
            name=filename,
            source_type=KnowledgeDocumentSourceType.PDF.value,
            content=content,
            character_count=len(content),
            content_hash=content_hash,
        )

        await self._kb_repository.update(
            kb,
            document_count=kb.document_count + 1,
            total_characters=kb.total_characters + len(content),
        )

        return doc

    async def get_document(self, kb_id: UUID, doc_id: UUID) -> KnowledgeDocument:
        doc = await self._doc_repository.get_by_id(doc_id)
        if doc is None or doc.knowledge_base_id != kb_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Документ с ID {doc_id} не найден в этой базе знаний",
            )
        return doc

    async def get_kb_documents(self, kb_id: UUID) -> Sequence[KnowledgeDocument]:
        await self.get_knowledge_base(kb_id)
        return await self._doc_repository.get_by_knowledge_base_id(kb_id)

    async def delete_document(self, kb_id: UUID, doc_id: UUID) -> None:
        kb = await self.get_knowledge_base(kb_id)
        doc = await self.get_document(kb_id, doc_id)

        await self._doc_repository.delete(doc_id)

        new_count = max(0, kb.document_count - 1)
        new_chars = max(0, kb.total_characters - doc.character_count)
        await self._kb_repository.update(
            kb,
            document_count=new_count,
            total_characters=new_chars,
        )

    # ============================================
    # Content retrieval (for AgentNode)
    # ============================================

    async def get_combined_content(self, kb_ids: list[UUID]) -> str:
        """
        Get the combined text of all documents in the given knowledge bases.

        Used by AgentNode to inject into the system prompt. The limit is enforced
        at document upload time; the check here is only a safety net for when
        several KBs are attached at once and their combined size is large.

        Raises:
            HTTPException 422: combined size of multiple KBs exceeds the limit
        """
        if not kb_ids:
            return ""

        content = await self._doc_repository.get_all_content_by_kb_ids(kb_ids)

        if len(content) > MAX_COMBINED_CHARACTERS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Суммарный объём подключённых баз знаний ({len(content):,} символов) "
                    f"превышает лимит ({MAX_COMBINED_CHARACTERS:,} символов). "
                    "Подключите меньше баз знаний к этой ноде."
                ),
            )

        return content


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _check_size_limit(current_total: int, new_content_size: int) -> None:
    """Raise HTTP 422 if adding a new document would exceed the KB size limit."""
    resulting_total = current_total + new_content_size
    if resulting_total > MAX_COMBINED_CHARACTERS:
        remaining = max(0, MAX_COMBINED_CHARACTERS - current_total)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Документ слишком большой: добавление {new_content_size:,} символов "
                f"превысит лимит базы знаний ({MAX_COMBINED_CHARACTERS:,} символов). "
                f"Доступно ещё {remaining:,} символов. "
                "Сократите документ или удалите другие документы из базы знаний."
            ),
        )
