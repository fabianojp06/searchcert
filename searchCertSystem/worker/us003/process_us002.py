"""
US003 — Consome o JSON do US002: baixa cada PDF, extrai texto/datas e gera payload consolidado.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from searchCertSystem.worker.us002.drive_client import DriveClient
from searchCertSystem.worker.us003.date_extract import extract_issue_and_expiry_dates
from searchCertSystem.worker.us003.drive_download import download_pdf_bytes
from searchCertSystem.worker.us003.pdf_text import count_pages, extract_text_from_pdf_bytes


@dataclass(frozen=True)
class Us003Config:
    max_pages: int | None = 2
    debug_dir: str | None = None
    debug_text_chars: int = 2000


def _utcnow() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def process_us002_payload(
    drive: DriveClient,
    us002_payload: dict[str, Any],
    *,
    config: Us003Config,
) -> dict[str, Any]:
    out_colabs: list[dict[str, Any]] = []

    for colab in us002_payload.get("colaboradores", []) or []:
        out_certs: list[dict[str, Any]] = []
        for cert in colab.get("certificacoes", []) or []:
            out_pdfs: list[dict[str, Any]] = []
            for pdf in cert.get("pdfs", []) or []:
                file_id = pdf.get("file_id")
                file_name = pdf.get("file_name")
                web_view_link = pdf.get("web_view_link")
                if not file_id:
                    continue

                entry: dict[str, Any] = {
                    "file_id": file_id,
                    "file_name": file_name,
                    "web_view_link": web_view_link,
                }
                try:
                    pdf_bytes = download_pdf_bytes(drive, file_id)
                    entry["pdf_pages"] = count_pages(pdf_bytes)
                    text = extract_text_from_pdf_bytes(pdf_bytes, max_pages=config.max_pages)
                    entry["text_len"] = len(text or "")
                    if (config.debug_dir and (text is not None)) or (entry["text_len"] == 0):
                        dbg_dir = Path(config.debug_dir or "output/us003_debug")
                        dbg_dir.mkdir(parents=True, exist_ok=True)
                        safe_name = (file_name or file_id).replace("\\", "_").replace("/", "_")
                        dump_path = dbg_dir / f"{safe_name}.{file_id}.txt"
                        snippet = (text or "")[: config.debug_text_chars]
                        dump_path.write_text(snippet, encoding="utf-8")
                        entry["debug_text_path"] = str(dump_path)
                    extracted = extract_issue_and_expiry_dates(text)
                    entry.update(extracted.to_json())
                    entry["status"] = "ok"
                except Exception as e:  # noqa: BLE001
                    entry["status"] = "error"
                    entry["error"] = str(e)
                out_pdfs.append(entry)

            out_certs.append(
                {
                    "nome": cert.get("nome"),
                    "cert_folder_id": cert.get("cert_folder_id"),
                    "pdfs": out_pdfs,
                }
            )

        out_colabs.append(
            {
                "nome": colab.get("nome"),
                "colaborador_folder_id": colab.get("colaborador_folder_id"),
                "certificacoes": out_certs,
            }
        )

    return {
        "generated_at": _utcnow(),
        "source": {
            "us002_generated_at": us002_payload.get("generated_at"),
            "root_folder_id": us002_payload.get("root_folder_id"),
        },
        "colaboradores": out_colabs,
    }

