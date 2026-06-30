"""Text extraction from PDF files via pdfplumber."""

import io
import re

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]


def extract_text_from_pdf(file_content: bytes, max_pages: int | None = None) -> str:
    if pdfplumber is None:
        raise ImportError("pdfplumber не установлен. Установите через: uv add pdfplumber")

    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            if max_pages is not None and len(pdf.pages) > max_pages:
                raise ValueError(
                    f"PDF содержит слишком много страниц ({len(pdf.pages)} > {max_pages})"
                )
            pages_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text.strip())

            if not pages_text:
                raise ValueError("PDF не содержит текста (возможно, это сканированный документ)")

            raw_text = "\n\n".join(pages_text)
            return clean_text(raw_text)

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Не удалось прочитать PDF файл: {e}") from e


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()
