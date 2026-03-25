from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_role_key: str


def _headers(cfg: SupabaseConfig, *, prefer: str) -> dict[str, str]:
    return {
        "apikey": cfg.service_role_key,
        "Authorization": f"Bearer {cfg.service_role_key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def upsert_colaborador(
    cfg: SupabaseConfig,
    *,
    nome: str,
    link_pasta: str,
) -> str:
    """
    Upsert em `colaboradores` usando `link_pasta` como chave única.
    Retorna o `id` UUID do colaborador.
    """
    endpoint = cfg.url.rstrip("/") + "/rest/v1/colaboradores"
    params = {"on_conflict": "link_pasta", "select": "id"}
    payload = [{"nome": nome, "link_pasta": link_pasta}]

    resp = requests.post(
        endpoint,
        params=params,
        headers=_headers(cfg, prefer="resolution=merge-duplicates,return=representation"),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data or not isinstance(data, list) or not data[0].get("id"):
        raise RuntimeError("Supabase não retornou id do colaborador no upsert.")
    return str(data[0]["id"])


def upsert_certificacao(
    cfg: SupabaseConfig,
    *,
    colaborador_id: str,
    nome_certificado: str,
    data_emissao: str | None,
    data_validade: str | None,
    link_pdf: str,
    pdf_file_id: str | None,
    pdf_file_name: str | None,
) -> None:
    """
    Upsert em `certificacoes` preferindo `pdf_file_id` (UNIQUE) quando disponível.
    Se `pdf_file_id` não existir, faz insert simples (pode duplicar se rodar 2x).
    """
    endpoint = cfg.url.rstrip("/") + "/rest/v1/certificacoes"
    payload = [
        {
            "colaborador_id": colaborador_id,
            "nome_certificado": nome_certificado,
            "data_emissao": data_emissao,
            "data_validade": data_validade,
            "link_pdf": link_pdf,
            "pdf_file_id": pdf_file_id,
            "pdf_file_name": pdf_file_name,
        }
    ]

    if pdf_file_id:
        resp = requests.post(
            endpoint,
            params={"on_conflict": "pdf_file_id"},
            headers=_headers(cfg, prefer="resolution=merge-duplicates,return=minimal"),
            json=payload,
            timeout=30,
        )
    else:
        resp = requests.post(
            endpoint,
            headers=_headers(cfg, prefer="return=minimal"),
            json=payload,
            timeout=30,
        )
    resp.raise_for_status()

