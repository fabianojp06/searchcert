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
    get_curriculo_by_person,
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
    <title>CertiBot</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #0b1220;
        --panel: #111a2a;
        --panel-2: #0f1725;
        --border: #263246;
        --text: #e7edf7;
        --muted: #9fb0c8;
        --accent: #4f8cff;
        --accent-2: #2f6fe3;
        --user: #1e293b;
        --bot: #152033;
        --ok: #1f9d63;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: Inter, Segoe UI, Roboto, Arial, sans-serif;
        color: var(--text);
        background: radial-gradient(1200px 400px at 15% -10%, #1a2d4f 0%, transparent 60%),
                    radial-gradient(900px 300px at 90% -20%, #20304f 0%, transparent 60%),
                    var(--bg);
      }
      .wrap {
        max-width: 980px;
        margin: 0 auto;
        padding: 28px 16px;
      }
      .app {
        border: 1px solid var(--border);
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.01));
        box-shadow: 0 14px 40px rgba(0,0,0,.35);
        overflow: hidden;
      }
      .topbar {
        padding: 14px 16px;
        background: var(--panel);
        border-bottom: 1px solid var(--border);
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .brand {
        font-weight: 700;
        letter-spacing: .2px;
      }
      .badge {
        font-size: 12px;
        color: #b8c6da;
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 4px 8px;
      }
      .chat {
        min-height: 420px;
        max-height: 62vh;
        overflow: auto;
        padding: 16px;
        background: var(--panel-2);
      }
      .msg {
        margin-bottom: 12px;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .msg.user { align-items: flex-end; }
      .msg.bot { align-items: flex-start; }
      .bubble {
        max-width: min(760px, 92%);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 10px 12px;
        white-space: pre-wrap;
        word-break: break-word;
        line-height: 1.45;
      }
      .msg.user .bubble { background: var(--user); }
      .msg.bot .bubble { background: var(--bot); }
      .meta {
        font-size: 12px;
        color: var(--muted);
      }
      .evidence {
        max-width: min(760px, 92%);
        display: grid;
        gap: 8px;
      }
      .ev-card {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 8px 10px;
        background: #101b2d;
      }
      .ev-card a {
        color: #b9d2ff;
        text-decoration: none;
        word-break: break-all;
      }
      .ev-card a:hover { text-decoration: underline; }
      .composer {
        border-top: 1px solid var(--border);
        background: var(--panel);
        padding: 12px;
      }
      .row {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 8px;
      }
      input {
        width: 100%;
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid var(--border);
        background: #0d1625;
        color: var(--text);
        outline: none;
      }
      input:focus { border-color: var(--accent); }
      button {
        border: 1px solid transparent;
        border-radius: 10px;
        padding: 0 16px;
        font-weight: 600;
        color: white;
        background: linear-gradient(180deg, var(--accent), var(--accent-2));
        cursor: pointer;
      }
      button:disabled { opacity: .6; cursor: not-allowed; }
      .hint {
        margin-top: 8px;
        color: var(--muted);
        font-size: 12px;
      }
      code {
        background: #0b1421;
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 1px 6px;
      }
      .typing { color: var(--ok); font-size: 12px; margin-top: 6px; display: none; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="app">
        <div class="topbar">
          <div class="brand">CertiBot</div>
          <div class="badge">RH • Consulta de Certificações</div>
        </div>
        <div id="chat" class="chat"></div>
        <div class="composer">
          <div class="row">
            <input id="msg" placeholder="Ex.: certificações ativas do João Silva" />
            <button id="send">Enviar</button>
          </div>
          <div id="typing" class="typing">Consultando base de certificações...</div>
          <div class="hint">
            Exemplos: <code>certificações ativas do João Silva</code> • <code>quem tem certificação PO válida hoje</code>
          </div>
        </div>
      </div>
    </div>
    <script>
      const $chat = document.getElementById('chat');
      const $msg = document.getElementById('msg');
      const $send = document.getElementById('send');
      const $typing = document.getElementById('typing');

      function nowLabel() {
        const d = new Date();
        return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      }

      function appendMessage(kind, text, evidence) {
        const wrap = document.createElement('div');
        wrap.className = 'msg ' + kind;

        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = (kind === 'user' ? 'Você' : 'CertiBot') + ' • ' + nowLabel();

        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.textContent = text || '';

        wrap.appendChild(meta);
        wrap.appendChild(bubble);

        if (Array.isArray(evidence) && evidence.length) {
          const ev = document.createElement('div');
          ev.className = 'evidence';
          for (const item of evidence) {
            const c = document.createElement('div');
            c.className = 'ev-card';
            const a = document.createElement('a');
            a.href = item.url;
            a.target = '_blank';
            a.rel = 'noreferrer';
            a.textContent = (item.label || 'Evidência') + ' → ' + (item.url || '');
            c.appendChild(a);
            ev.appendChild(c);
          }
          wrap.appendChild(ev);
        }

        $chat.appendChild(wrap);
        $chat.scrollTop = $chat.scrollHeight;
      }

      async function send() {
        const message = ($msg.value || '').trim();
        if (!message) return;
        appendMessage('user', message);
        $msg.value = '';
        $send.disabled = true;
        $typing.style.display = 'block';

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
            appendMessage('bot', (data && data.detail) ? String(data.detail) : (text || ('Erro HTTP ' + res.status)));
            return;
          }
          appendMessage('bot', (data && data.answer) ? data.answer : text, (data && data.evidence) ? data.evidence : []);
        } catch (err) {
          appendMessage('bot', String(err));
        } finally {
          $send.disabled = false;
          $typing.style.display = 'none';
          $msg.focus();
        }
      }

      $send.addEventListener('click', send);
      $msg.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
      appendMessage('bot', 'Olá! Posso consultar certificações ativas, expiradas, vencimentos do ano e busca por PO/SM.');
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
                "- 'Me mostre todos os funcionários com certificações ativas.'\n"
                "- 'Exiba o currículo de Fabiano Santos Garcia.'"
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

    if pq.kind == "curriculo_by_person":
        if not person_name:
            raise HTTPException(status_code=400, detail="Não consegui identificar o nome do colaborador para currículo.")
        row = get_curriculo_by_person(cfg, person_name)
        if not row:
            return ChatResponse(answer=f"Não encontrei currículo para '{person_name}'.", evidence=[], raw={"intent": pq.kind})
        nome = row.get("colaborador_nome") or person_name
        link = row.get("link_pdf")
        if not link:
            return ChatResponse(answer=f"Encontrei referência de currículo de '{nome}', mas sem link.", evidence=[], raw={"intent": pq.kind})
        return ChatResponse(
            answer=f"Encontrei o currículo de {nome}.",
            evidence=[EvidenceLink(label=f"Currículo - {nome}", url=link)],
            raw={"intent": pq.kind},
        )

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
            return ChatResponse(
                answer="No momento, o funcionário não tem certificações.",
                evidence=[],
                raw={"intent": pq.kind},
            )

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

