from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any

from .drive_client import FOLDER_MIME_TYPE, PDF_MIME_TYPE, DriveClient
from .types import PdfLink


@dataclass(frozen=True)
class MapperConfig:
    root_folder_id: str


def _as_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _drive_file_url(file_id: str) -> str:
    # Fallback caso webViewLink não venha por permissão/campos
    return f"https://drive.google.com/file/d/{file_id}/view"


def list_direct_folders(drive: DriveClient, parent_id: str) -> list[dict[str, str]]:
    folders: list[dict[str, str]] = []
    for item in drive.iter_children(parent_id, mime_type=FOLDER_MIME_TYPE):
        if not item.get("id") or not item.get("name"):
            continue
        folders.append({"id": item["id"], "name": item["name"]})
    return sorted(folders, key=lambda x: x["name"].lower())


def collect_descendant_pdfs(drive: DriveClient, start_folder_id: str) -> list[PdfLink]:
    pdfs: list[PdfLink] = []
    stack: list[str] = [start_folder_id]
    visited: set[str] = set()

    while stack:
        folder_id = stack.pop()
        if folder_id in visited:
            continue
        visited.add(folder_id)

        # PDFs diretamente na pasta
        for item in drive.iter_children(folder_id, mime_type=PDF_MIME_TYPE):
            file_id = item.get("id")
            name = item.get("name")
            if not file_id or not name:
                continue
            web_view_link = item.get("webViewLink") or _drive_file_url(file_id)
            pdfs.append(PdfLink(file_id=file_id, file_name=name, web_view_link=web_view_link))

        # Subpastas (para permitir níveis futuros)
        for sub in drive.iter_children(folder_id, mime_type=FOLDER_MIME_TYPE):
            sub_id = sub.get("id")
            if sub_id:
                stack.append(sub_id)

    pdfs.sort(key=lambda p: (p.file_name.lower(), p.file_id))
    return pdfs


def map_drive_structure(
    drive: DriveClient,
    config: MapperConfig,
    *,
    include_links: bool = True,
) -> dict[str, Any]:
    colaboradores = list_direct_folders(drive, config.root_folder_id)

    out_colabs: list[dict[str, Any]] = []
    for colab in colaboradores:
        colab_id = colab["id"]
        colab_name = colab["name"]

        cert_folders = list_direct_folders(drive, colab_id)
        out_certs: list[dict[str, Any]] = []
        for cert in cert_folders:
            cert_id = cert["id"]
            cert_name = cert["name"]

            cert_entry: dict[str, Any] = {
                "nome": cert_name,
                "cert_folder_id": cert_id,
            }
            if include_links:
                cert_entry["pdfs"] = [p.to_json() for p in collect_descendant_pdfs(drive, cert_id)]
            out_certs.append(cert_entry)

        out_colabs.append(
            {
                "nome": colab_name,
                "colaborador_folder_id": colab_id,
                "certificacoes": out_certs,
            }
        )

    return {
        "generated_at": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        "root_folder_id": config.root_folder_id,
        "colaboradores": out_colabs,
    }

