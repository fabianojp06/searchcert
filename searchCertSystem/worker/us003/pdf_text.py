from __future__ import annotations

import fitz  # PyMuPDF


def extract_text_from_pdf_bytes(pdf_bytes: bytes, *, max_pages: int | None = None) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        n = doc.page_count
        if max_pages is not None:
            n = min(n, max_pages)
        parts: list[str] = []
        for i in range(n):
            page = doc.load_page(i)
            parts.append(page.get_text("text"))
        return "\n".join(parts)
    finally:
        doc.close()


def count_pages(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()

