"""API CRUD tests for knowledge bases and their documents — status checks only."""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest_asyncio


def _minimal_pdf(text: str = "Hello PDF") -> bytes:
    """Build a tiny valid one-page PDF with extractable text (for the upload test)."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    ]
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode("latin-1") + b") Tj ET"
    objs.append(
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_pos = out.tell()
    count = len(objs) + 1
    out.write(f"xref\n0 {count}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {count} /Root 1 0 R >>\n".encode())
    out.write(f"startxref\n{xref_pos}\n%%EOF".encode())
    return out.getvalue()


async def _create_kb(client, headers, project_id, name="My KB"):
    """Create a knowledge base and return the response."""
    return await client.post(
        "/api/knowledge-bases/",
        json={"projectId": str(project_id), "name": name},
        headers=headers,
    )


@pytest_asyncio.fixture
async def knowledge_base(client, auth_user, auth_headers) -> str:
    """Per-test setup: create a knowledge base and return its id (@BeforeEach)."""
    resp = await _create_kb(client, auth_headers, auth_user.project_id)
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_knowledge_base(client, auth_user, auth_headers) -> None:
    """POST /api/knowledge-bases/ → 201."""
    # Arrange
    payload = {"projectId": str(auth_user.project_id), "name": "Docs"}

    # Act
    resp = await client.post("/api/knowledge-bases/", json=payload, headers=auth_headers)

    # Assert
    assert resp.status_code == 201


async def test_get_knowledge_base(client, auth_headers, knowledge_base) -> None:
    """GET /api/knowledge-bases/{id} → 200."""
    # Act
    resp = await client.get(f"/api/knowledge-bases/{knowledge_base}", headers=auth_headers)

    # Assert
    assert resp.status_code == 200


async def test_update_knowledge_base(client, auth_headers, knowledge_base) -> None:
    """PATCH /api/knowledge-bases/{id} → 200."""
    # Act
    resp = await client.patch(
        f"/api/knowledge-bases/{knowledge_base}",
        json={"name": "Renamed KB"},
        headers=auth_headers,
    )

    # Assert
    assert resp.status_code == 200


async def test_delete_knowledge_base(client, auth_headers, knowledge_base) -> None:
    """DELETE /api/knowledge-bases/{id} → 204."""
    # Act
    resp = await client.delete(f"/api/knowledge-bases/{knowledge_base}", headers=auth_headers)

    # Assert
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


async def _create_text_doc(client, headers, kb_id, name="Doc", content="hello"):
    """Create a text document in a KB and return the response."""
    return await client.post(
        f"/api/knowledge-bases/{kb_id}/documents/text",
        json={"name": name, "content": content},
        headers=headers,
    )


@pytest_asyncio.fixture
async def text_document(client, auth_headers, knowledge_base) -> SimpleNamespace:
    """Per-test setup: a KB with one text document. Returns kb_id + doc_id."""
    resp = await _create_text_doc(client, auth_headers, knowledge_base)
    assert resp.status_code == 201
    return SimpleNamespace(kb_id=knowledge_base, doc_id=resp.json()["id"])


async def test_create_text_document(client, auth_headers, knowledge_base) -> None:
    """POST /api/knowledge-bases/{kb}/documents/text → 201."""
    # Act
    resp = await _create_text_doc(client, auth_headers, knowledge_base, content="some text")

    # Assert
    assert resp.status_code == 201


async def test_list_documents(client, auth_headers, text_document) -> None:
    """GET /api/knowledge-bases/{kb}/documents → 200."""
    # Act
    resp = await client.get(
        f"/api/knowledge-bases/{text_document.kb_id}/documents", headers=auth_headers
    )

    # Assert
    assert resp.status_code == 200


async def test_get_document(client, auth_headers, text_document) -> None:
    """GET /api/knowledge-bases/{kb}/documents/{id} → 200."""
    # Act
    resp = await client.get(
        f"/api/knowledge-bases/{text_document.kb_id}/documents/{text_document.doc_id}",
        headers=auth_headers,
    )

    # Assert
    assert resp.status_code == 200


async def test_delete_document(client, auth_headers, text_document) -> None:
    """DELETE /api/knowledge-bases/{kb}/documents/{id} → 204."""
    # Act
    resp = await client.delete(
        f"/api/knowledge-bases/{text_document.kb_id}/documents/{text_document.doc_id}",
        headers=auth_headers,
    )

    # Assert
    assert resp.status_code == 204


async def test_upload_pdf_document(client, auth_headers, knowledge_base) -> None:
    """POST /api/knowledge-bases/{kb}/documents/pdf (multipart) → 201."""
    # Arrange
    pdf_bytes = _minimal_pdf()

    # Act
    resp = await client.post(
        f"/api/knowledge-bases/{knowledge_base}/documents/pdf",
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )

    # Assert
    assert resp.status_code == 201
