"""Tipos compartilhados do US002 (metadados de arquivo Drive e links de PDF)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class DriveFileDict(TypedDict, total=False):
    id: str
    name: str
    mimeType: str
    webViewLink: str


@dataclass(frozen=True)
class PdfLink:
    file_id: str
    file_name: str
    web_view_link: str | None

    def to_json(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "web_view_link": self.web_view_link,
        }

