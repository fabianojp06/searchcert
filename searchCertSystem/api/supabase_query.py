from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from requests import HTTPError


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_role_key: str


def _headers(cfg: SupabaseConfig) -> dict[str, str]:
    return {
        "apikey": cfg.service_role_key,
        "Authorization": f"Bearer {cfg.service_role_key}",
        "Content-Type": "application/json",
    }


def _get(cfg: SupabaseConfig, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    endpoint = cfg.url.rstrip("/") + path
    resp = requests.get(endpoint, headers=_headers(cfg), params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("Resposta inesperada do Supabase (não é lista).")
    return data


def _cert_aliases(cert_name: str) -> list[str]:
    """
    Expande aliases comuns de certificações.
    Ex.: 'PO' -> ['PO', 'Product Owner'] e 'Product Owner' -> ['Product Owner', 'PO'].
    """
    raw = cert_name.strip()
    norm = raw.lower().strip(". ").replace("-", " ")

    mapping = {
        "po": ["PO", "Product Owner"],
        "product owner": ["Product Owner", "PO"],
        "sm": ["SM", "Scrum Master"],
        "scrum master": ["Scrum Master", "SM"],
    }

    return mapping.get(norm, [raw])


def _get_certifications_fallback(cfg: SupabaseConfig, params: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Fallback quando a view `v_certificacoes` ainda não existe.
    Faz join via PostgREST usando relacionamento FK.
    """
    # certificacoes + join colaboradores (inner)
    select = "nome_certificado,data_emissao,data_validade,link_pdf,pdf_file_id,colaboradores!inner(nome)"
    params2 = dict(params)
    params2["select"] = select
    data = _get(cfg, "/rest/v1/certificacoes", params2)
    # normaliza shape para bater com o formato da view
    out: list[dict[str, Any]] = []
    for row in data:
        col = row.get("colaboradores") or {}
        out.append(
            {
                "colaborador_nome": col.get("nome"),
                "nome_certificado": row.get("nome_certificado"),
                "data_emissao": row.get("data_emissao"),
                "data_validade": row.get("data_validade"),
                "link_pdf": row.get("link_pdf"),
                "pdf_file_id": row.get("pdf_file_id"),
            }
        )
    return out


def list_active_certifications_by_person(cfg: SupabaseConfig, person_name: str) -> list[dict[str, Any]]:
    # Filtra por nome (ilike) e validade >= hoje OU null
    params = {
        "select": "colaborador_nome,nome_certificado,data_emissao,data_validade,link_pdf,pdf_file_id",
        "colaborador_nome": f"ilike.%{person_name}%",
        "or": "(data_validade.is.null,data_validade.gte.now())",
        "order": "data_validade.asc.nullslast,nome_certificado.asc",
    }
    try:
        return _get(cfg, "/rest/v1/v_certificacoes", params)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            # não existe a view; usa fallback
            params_fb = {
                "colaboradores.nome": f"ilike.%{person_name}%",
                "or": "(data_validade.is.null,data_validade.gte.now())",
                "order": "data_validade.asc.nullslast,nome_certificado.asc",
            }
            return _get_certifications_fallback(cfg, params_fb)
        raise


def list_all_people(cfg: SupabaseConfig) -> list[str]:
    rows = _get(cfg, "/rest/v1/colaboradores", {"select": "nome", "order": "nome.asc"})
    out: list[str] = []
    for r in rows:
        if r.get("nome"):
            out.append(str(r["nome"]))
    return out


def get_curriculo_by_person(cfg: SupabaseConfig, person_name: str) -> dict[str, Any] | None:
    """
    Busca currículo do colaborador por nome (ilike).
    Prioriza a view/tabela join via PostgREST.
    """
    params = {
        "select": "link_pdf,pdf_file_id,pdf_file_name,colaboradores!inner(nome)",
        "colaboradores.nome": f"ilike.%{person_name}%",
        "order": "updated_at.desc",
        "limit": "1",
    }
    rows = _get(cfg, "/rest/v1/curriculos", params)
    if not rows:
        return None
    row = rows[0]
    col = row.get("colaboradores") or {}
    return {
        "colaborador_nome": col.get("nome"),
        "link_pdf": row.get("link_pdf"),
        "pdf_file_id": row.get("pdf_file_id"),
        "pdf_file_name": row.get("pdf_file_name"),
    }


def list_all_active_certifications(cfg: SupabaseConfig) -> list[dict[str, Any]]:
    params = {
        "select": "colaborador_nome,nome_certificado,data_emissao,data_validade,link_pdf,pdf_file_id",
        "or": "(data_validade.is.null,data_validade.gte.now())",
        "order": "colaborador_nome.asc,nome_certificado.asc,data_validade.asc.nullslast",
    }
    try:
        return _get(cfg, "/rest/v1/v_certificacoes", params)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            params_fb = {
                "or": "(data_validade.is.null,data_validade.gte.now())",
                "order": "colaboradores.nome.asc,nome_certificado.asc,data_validade.asc.nullslast",
            }
            return _get_certifications_fallback(cfg, params_fb)
        raise


def list_expired_certifications_by_person(cfg: SupabaseConfig, person_name: str) -> list[dict[str, Any]]:
    params = {
        "select": "colaborador_nome,nome_certificado,data_emissao,data_validade,link_pdf,pdf_file_id",
        "colaborador_nome": f"ilike.%{person_name}%",
        "data_validade": "lt.now()",
        "order": "data_validade.desc,nome_certificado.asc",
    }
    try:
        return _get(cfg, "/rest/v1/v_certificacoes", params)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            params_fb = {
                "colaboradores.nome": f"ilike.%{person_name}%",
                "data_validade": "lt.now()",
                "order": "data_validade.desc,nome_certificado.asc",
            }
            return _get_certifications_fallback(cfg, params_fb)
        raise


def list_expiring_year_by_person(cfg: SupabaseConfig, person_name: str, year: int) -> list[dict[str, Any]]:
    # year = -1 means current year (resolve in caller)
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    params = {
        "select": "colaborador_nome,nome_certificado,data_emissao,data_validade,link_pdf,pdf_file_id",
        "colaborador_nome": f"ilike.%{person_name}%",
        "data_validade": f"gte.{start}",
        "order": "data_validade.asc,nome_certificado.asc",
    }
    try:
        rows = _get(cfg, "/rest/v1/v_certificacoes", params)
        # client-side filter end bound
        return [r for r in rows if (r.get("data_validade") or "") <= end]
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            rows = _get_certifications_fallback(cfg, {"colaboradores.nome": f"ilike.%{person_name}%", "data_validade": f"gte.{start}"})
            return [r for r in rows if (r.get("data_validade") or "") <= end]
        raise


def count_people_with_cert_active(cfg: SupabaseConfig, cert_name: str) -> int:
    rows = list_people_with_valid_certification(cfg, cert_name)
    people = {r.get("colaborador_nome") for r in rows if r.get("colaborador_nome")}
    return len(people)


def list_people_with_cert_expired(cfg: SupabaseConfig, cert_name: str) -> list[dict[str, Any]]:
    aliases = _cert_aliases(cert_name)
    merged: dict[str, dict[str, Any]] = {}

    def _add(rows: list[dict[str, Any]]) -> None:
        for r in rows:
            key = str(r.get("pdf_file_id") or "") or f"{r.get('colaborador_nome')}::{r.get('nome_certificado')}::{r.get('link_pdf')}"
            merged[key] = r

    for alias in aliases:
        params = {
            "select": "colaborador_nome,nome_certificado,data_emissao,data_validade,link_pdf,pdf_file_id",
            "nome_certificado": f"ilike.%{alias}%",
            "data_validade": "lt.now()",
            "order": "colaborador_nome.asc,data_validade.desc",
        }
        try:
            _add(_get(cfg, "/rest/v1/v_certificacoes", params))
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                _add(_get_certifications_fallback(cfg, {"nome_certificado": f"ilike.%{alias}%", "data_validade": "lt.now()", "order": "colaboradores.nome.asc,data_validade.desc"}))
            else:
                raise

    rows = list(merged.values())
    rows.sort(key=lambda r: ((r.get("colaborador_nome") or "").lower(), (r.get("data_validade") or "0000-00-00"), (r.get("nome_certificado") or "").lower()))
    return rows


def list_people_with_valid_certification(cfg: SupabaseConfig, cert_name: str) -> list[dict[str, Any]]:
    aliases = _cert_aliases(cert_name)
    # Evita `or=` complexo (que varia entre versões do PostgREST).
    # Faz 1 chamada por alias e mescla resultados.
    merged: dict[str, dict[str, Any]] = {}

    def _add(rows: list[dict[str, Any]]) -> None:
        for r in rows:
            key = str(r.get("pdf_file_id") or "") or f"{r.get('colaborador_nome')}::{r.get('nome_certificado')}::{r.get('link_pdf')}"
            merged[key] = r

    for alias in aliases:
        params = {
            "select": "colaborador_nome,nome_certificado,data_emissao,data_validade,link_pdf,pdf_file_id",
            "nome_certificado": f"ilike.%{alias}%",
            "or": "(data_validade.is.null,data_validade.gte.now())",
            "order": "colaborador_nome.asc,data_validade.asc.nullslast",
        }
        try:
            _add(_get(cfg, "/rest/v1/v_certificacoes", params))
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                params_fb = {
                    "nome_certificado": f"ilike.%{alias}%",
                    "or": "(data_validade.is.null,data_validade.gte.now())",
                    "order": "colaboradores.nome.asc,data_validade.asc.nullslast",
                }
                _add(_get_certifications_fallback(cfg, params_fb))
            else:
                raise

    rows = list(merged.values())
    rows.sort(key=lambda r: ((r.get("colaborador_nome") or "").lower(), (r.get("data_validade") or "9999-12-31"), (r.get("nome_certificado") or "").lower()))
    return rows

