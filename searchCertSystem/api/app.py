from __future__ import annotations

import datetime as _dt
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from searchCertSystem.api.nlp import best_match_person, parse_query
from searchCertSystem.api.supabase_query import (
    SupabaseConfig,
    list_active_certifications_by_person,
    list_all_active_certifications,
    list_all_people,
    list_expired_certifications_by_person,
    list_expiring_year_by_person,
    list_people_with_cert_expired,
    list_people_with_valid_certification,
    count_people_with_cert_active,
)


load_dotenv()

app = FastAPI(title="CertiBot API", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class EvidenceLink(BaseModel):
    label: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    evidence: list[EvidenceLink] = []
    raw: dict[str, Any] | None = None


def _supabase_cfg() -> SupabaseConfig:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase não configurado (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).")
    return SupabaseConfig(url=url, service_role_key=key)


def _fmt_date(d: str | None) -> str:
    # PostgREST vem como YYYY-MM-DD
    if not d:
        return "-"
    if len(d) == 10 and d[4] == "-" and d[7] == "-":
        yyyy, mm, dd = d.split("-")
        return f"{dd}/{mm}/{yyyy}"
    return d


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


_CHAT_HTML = """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>CertiBot (MVP)</title>
    <style>
      :root { color-scheme: light dark; }
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; }
      .wrap { max-width: 900px; margin: 0 auto; padding: 16px; }
      .card { border: 1px solid rgba(127,127,127,.35); border-radius: 12px; padding: 12px; }
      .row { display: flex; gap: 8px; align-items: center; }
      input { flex: 1; padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(127,127,127,.35); }
      button { padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(127,127,127,.35); cursor: pointer; }
      pre { white-space: pre-wrap; word-break: break-word; margin: 12px 0 0; }
      .hint { opacity: .8; font-size: 13px; margin-top: 8px; }
      a { word-break: break-word; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h2>CertiBot (MVP)</h2>
      <div class="card">
        <div class="row">
          <input id="msg" placeholder="Ex: certificações ativas do Fabiano Garcia" />
          <button id="send">Enviar</button>
        </div>
        <div class="hint">
          Exemplos: <code>certificações ativas do João Silva</code> • <code>quem tem certificação Product Owner válida hoje</code>
        </div>
        <pre id="out"></pre>
        <div id="links"></div>
      </div>
    </div>
    <script>
      const $msg = document.getElementById('msg');
      const $out = document.getElementById('out');
      const $links = document.getElementById('links');
      const $send = document.getElementById('send');

      async function send() {
        const message = ($msg.value || '').trim();
        if (!message) return;
        $out.textContent = 'Consultando...';
        $links.innerHTML = '';
        try {
          const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
            body: JSON.stringify({ message }),
          });
          const text = await res.text();
          let data = null;
          try { data = JSON.parse(text); } catch (e) { data = null; }
          if (!res.ok) {
            $out.textContent = (data && data.detail) ? String(data.detail) : (text || ('Erro HTTP ' + res.status));
            return;
          }
          $out.textContent = (data && data.answer) ? data.answer : text;
          const ev = (data && data.evidence) ? data.evidence : [];
          if (ev.length) {
            const ul = document.createElement('ul');
            for (const e of ev) {
              const li = document.createElement('li');
              const a = document.createElement('a');
              a.href = e.url;
              a.target = '_blank';
              a.rel = 'noreferrer';
              a.textContent = e.label + ' → ' + e.url;
              li.appendChild(a);
              ul.appendChild(li);
            }
            $links.appendChild(ul);
          }
        } catch (err) {
          $out.textContent = String(err);
        }
      }

      $send.addEventListener('click', send);
      $msg.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
    </script>
  </body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(_CHAT_HTML)


@app.get("/chat")
def chat_get() -> RedirectResponse:
    # Browser acessa por GET; redireciona para a UI
    return RedirectResponse(url="/", status_code=307)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    pq = parse_query(req.message)
    if not pq:
        raise HTTPException(
            status_code=400,
            detail=(
                "Não entendi.\n\n"
                "Exemplos:\n"
                "- 'Quais as certificações vigentes do João Silva?'\n"
                "- 'Quais as certs do João Silva?'\n"
                "- 'Joao silva tem cert ativa?'\n"
                "- 'Quem tem certificação PO válida hoje?'\n"
                "- 'Quantos POs certificados temos hoje?'\n"
                "- 'Me mostre todos os funcionários com certificações ativas.'"
            ),
        )

    cfg = _supabase_cfg()

    # resolve person with fuzzy matching (para aguentar variações/typos/sem acento)
    person_name = None
    if pq.person_hint:
        candidates = list_all_people(cfg)
        # tenta casar pelo hint; se falhar, tenta casar pela frase inteira (nome em qualquer posição)
        person_name = best_match_person(pq.person_hint, candidates) or best_match_person(req.message, candidates) or pq.person_hint

    if pq.kind == "list_all_active":
        rows = list_all_active_certifications(cfg)
        if not rows:
            return ChatResponse(answer="Não encontrei certificações ativas no momento.", evidence=[], raw={"intent": pq.kind})
        lines: list[str] = ["Funcionários com certificações ativas:"]
        evidence: list[EvidenceLink] = []
        for r in rows:
            nome = r.get("colaborador_nome") or "-"
            cert = r.get("nome_certificado") or "-"
            va = _fmt_date(r.get("data_validade"))
            lines.append(f"- {nome}: {cert} (Validade: {va})")
            link = r.get("link_pdf")
            if link:
                evidence.append(EvidenceLink(label=f"{nome} - {cert}", url=link))
        return ChatResponse(answer="\n".join(lines), evidence=evidence, raw={"intent": pq.kind, "count": len(rows)})

    if pq.kind == "count_people_with_cert_active":
        if not pq.cert_hint:
            raise HTTPException(status_code=400, detail="Faltou informar a certificação para contagem.")
        n = count_people_with_cert_active(cfg, pq.cert_hint)
        return ChatResponse(answer=f"Temos {n} pessoa(s) com '{pq.cert_hint}' válida hoje.", evidence=[], raw={"intent": pq.kind, "count": n})

    if pq.kind == "people_with_cert_active":
        if not pq.cert_hint:
            raise HTTPException(status_code=400, detail="Faltou informar a certificação.")
        rows = list_people_with_valid_certification(cfg, pq.cert_hint)
        if not rows:
            return ChatResponse(answer=f"Não encontrei ninguém com certificação '{pq.cert_hint}' válida hoje.", evidence=[], raw={"intent": pq.kind})

        lines: list[str] = [f"Pessoas com certificação '{pq.cert_hint}' válida hoje:"]
        evidence: list[EvidenceLink] = []
        for r in rows:
            nome = r.get("colaborador_nome") or "-"
            cert = r.get("nome_certificado") or pq.cert_hint
            va = _fmt_date(r.get("data_validade"))
            lines.append(f"- {nome} (Validade: {va})")
            link = r.get("link_pdf")
            if link:
                evidence.append(EvidenceLink(label=f"{nome} - {cert}", url=link))

        return ChatResponse(answer="\n".join(lines), evidence=evidence, raw={"intent": pq.kind, "count": len(rows)})

    if pq.kind == "people_with_cert_expired":
        if not pq.cert_hint:
            raise HTTPException(status_code=400, detail="Faltou informar a certificação.")
        rows = list_people_with_cert_expired(cfg, pq.cert_hint)
        if not rows:
            return ChatResponse(answer=f"Não encontrei ninguém com certificação '{pq.cert_hint}' expirada.", evidence=[], raw={"intent": pq.kind})
        lines: list[str] = [f"Pessoas com certificação '{pq.cert_hint}' expirada:"]
        evidence: list[EvidenceLink] = []
        for r in rows:
            nome = r.get("colaborador_nome") or "-"
            va = _fmt_date(r.get("data_validade"))
            lines.append(f"- {nome} (Venceu em: {va})")
            link = r.get("link_pdf")
            if link:
                evidence.append(EvidenceLink(label=f"{nome}", url=link))
        return ChatResponse(answer="\n".join(lines), evidence=evidence, raw={"intent": pq.kind, "count": len(rows)})

    if pq.kind == "certs_by_person_active":
        if not person_name:
            raise HTTPException(status_code=400, detail="Não consegui identificar o nome do colaborador.")
        rows = list_active_certifications_by_person(cfg, person_name)
        if not rows:
            return ChatResponse(answer=f"Não encontrei certificações ativas para '{person_name}'.", evidence=[], raw={"intent": pq.kind})

        lines: list[str] = [f"Certificações ativas de {rows[0].get('colaborador_nome') or person_name}:"]
        evidence: list[EvidenceLink] = []
        for r in rows:
            cert = r.get("nome_certificado") or "-"
            em = _fmt_date(r.get("data_emissao"))
            va = _fmt_date(r.get("data_validade"))
            lines.append(f"- {cert} (Emissão: {em} | Validade: {va})")
            link = r.get("link_pdf")
            if link:
                evidence.append(EvidenceLink(label=f"{cert}", url=link))

        return ChatResponse(answer="\n".join(lines), evidence=evidence, raw={"intent": pq.kind, "count": len(rows)})

    if pq.kind == "certs_by_person_expired":
        if not person_name:
            raise HTTPException(status_code=400, detail="Não consegui identificar o nome do colaborador.")
        rows = list_expired_certifications_by_person(cfg, person_name)
        if not rows:
            return ChatResponse(answer=f"Não encontrei certificações expiradas para '{person_name}'.", evidence=[], raw={"intent": pq.kind})
        lines: list[str] = [f"Certificações expiradas de {rows[0].get('colaborador_nome') or person_name}:"]
        evidence: list[EvidenceLink] = []
        for r in rows:
            cert = r.get("nome_certificado") or "-"
            va = _fmt_date(r.get("data_validade"))
            lines.append(f"- {cert} (Venceu em: {va})")
            link = r.get("link_pdf")
            if link:
                evidence.append(EvidenceLink(label=f"{cert}", url=link))
        return ChatResponse(answer="\n".join(lines), evidence=evidence, raw={"intent": pq.kind, "count": len(rows)})

    if pq.kind == "certs_by_person_expiring_year":
        if not person_name:
            raise HTTPException(status_code=400, detail="Não consegui identificar o nome do colaborador.")
        year = pq.year
        if year in (None, -1):
            year = _dt.date.today().year
        rows = list_expiring_year_by_person(cfg, person_name, year)
        if not rows:
            return ChatResponse(answer=f"Não encontrei certificações de '{person_name}' que vencem em {year}.", evidence=[], raw={"intent": pq.kind})
        lines: list[str] = [f"Certificações de {rows[0].get('colaborador_nome') or person_name} que vencem em {year}:"]
        evidence: list[EvidenceLink] = []
        for r in rows:
            cert = r.get("nome_certificado") or "-"
            va = _fmt_date(r.get("data_validade"))
            lines.append(f"- {cert} (Validade: {va})")
            link = r.get("link_pdf")
            if link:
                evidence.append(EvidenceLink(label=f"{cert}", url=link))
        return ChatResponse(answer="\n".join(lines), evidence=evidence, raw={"intent": pq.kind, "count": len(rows), "year": year})

    raise HTTPException(status_code=400, detail="Intent não suportada.")

