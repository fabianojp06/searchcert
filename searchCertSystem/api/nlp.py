from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz, process


def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s\.]", " ", s)  # mantém letras/números/underscore/ponto
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass(frozen=True)
class ParsedQuery:
    kind: str
    person_hint: str | None = None
    cert_hint: str | None = None
    year: int | None = None


_RE_CERT = re.compile(
    r"\b(?:certificacao|certificacoes|certificacao|certifica[cç][aã]o|certicacao|certicacoes|cert|certs)\b\s*(?:de\s+)?(.+?)(?:\s+(?:valida|ativa|vigente|em dia)\b|$)",
    re.IGNORECASE,
)
_RE_YEAR = re.compile(r"\b(20\d{2})\b")


def parse_query(message: str) -> ParsedQuery | None:
    raw = message.strip()
    n = normalize_text(raw)
    # remove pontuação final comum para facilitar heurísticas
    n = n.rstrip("?.!")

    # global intents
    if re.search(r"\bme mostre todos\b.*\bcertificacoes\b.*\bativas\b", n) or re.search(r"\btodos\b.*\bcertificacoes\b.*\bativas\b", n):
        return ParsedQuery(kind="list_all_active")

    # currículo / cv por pessoa
    if any(tok in n for tok in ("curriculo", "curriculum", "resume", " cv ")) and any(tok in n for tok in ("exiba", "mostre", "me mostre", "mostrar", "traga", "abre", "abrir")):
        m = re.search(r"\b(?:do|da|de)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\.]{2,})", message, flags=re.IGNORECASE)
        if m:
            return ParsedQuery(kind="curriculo_by_person", person_hint=m.group(1).strip())
        # fallback: tenta nome no começo
        m = re.match(r"^\s*([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\.]{2,})\b", message, flags=re.IGNORECASE)
        if m:
            return ParsedQuery(kind="curriculo_by_person", person_hint=m.group(1).strip())

    # contagem
    if n.startswith("quantos"):
        m = _RE_CERT.search(raw)
        cert = m.group(1).strip() if m else None
        if not cert:
            # padrões comuns: "quantos pos certificados"
            if " po " in f" {n} " or n.endswith(" po") or " product owner" in n:
                cert = "PO"
            elif " sm " in f" {n} " or n.endswith(" sm") or " scrum master" in n:
                cert = "SM"
        if cert:
            return ParsedQuery(kind="count_people_with_cert_active", cert_hint=cert)

    # who has X valid today / active / in date
    if any(n.startswith(p) for p in ("quem ", "alguem ", "alguém ", "tem alguem", "tem alguém", "existem", "existe")):
        m = _RE_CERT.search(raw)
        cert = m.group(1).strip() if m else None
        # também aceita frases tipo "POs certificados" sem "certificação"
        if not cert:
            if " po" in n or "p.o" in n or "product owner" in n or "dono do produto" in n:
                cert = "PO"
            elif " sm" in n or "scrum master" in n:
                cert = "SM"

        if cert:
            if "expirad" in n or "vencid" in n:
                return ParsedQuery(kind="people_with_cert_expired", cert_hint=cert)
            return ParsedQuery(kind="people_with_cert_active", cert_hint=cert)

    # "certificações ativas e Lucas Paquetá" → consulta por colaborador (antes do branch "cert X" global)
    # Usa `n` (sem acentos) para casar "certificacoes" mesmo quando o usuário digita "certificações"
    m_av_e = re.search(
        r"\b(?:certificacoes|certificacao|certs|certificados)\b.*?"
        r"\b(?:ativas?|vigentes?|validas?)\s+e\s+([a-zA-Z][a-zA-Z\s\.]{2,})",
        n,
        flags=re.IGNORECASE,
    )
    if m_av_e:
        ph = m_av_e.group(1).strip()
        ph_n = normalize_text(ph)
        # "e PO" / "e SM" continua sendo busca por tipo de certificação, não por nome
        if ph_n not in ("po", "sm", "pso", "cspo", "pmp", "itil", "aws") and not re.match(
            r"^(po|sm|p\.?o\.?|product owner|scrum master)\b",
            ph,
            re.IGNORECASE,
        ):
            if "expirad" in n or "vencid" in n:
                return ParsedQuery(kind="certs_by_person_expired", person_hint=ph)
            if "vencem" in n or "vence" in n:
                y: int | None = None
                my = _RE_YEAR.search(n)
                if my:
                    y = int(my.group(1))
                elif "este ano" in n:
                    y = -1
                return ParsedQuery(kind="certs_by_person_expiring_year", person_hint=ph, year=y)
            return ParsedQuery(kind="certs_by_person_active", person_hint=ph)

    # consultas curtas/telegráficas sem sujeito, ex:
    # - "certicação de PO"
    # - "certificacao PO ativa"
    # - "cert de sm"
    if any(tok in n.split(" ")[:3] for tok in ("certificacao", "certificacoes", "certificacao", "certicacao", "certificacao", "cert")) or n.startswith("cert"):
        m = _RE_CERT.search(raw)
        cert = m.group(1).strip() if m else None
        if not cert:
            if " po" in f" {n} " or "p.o" in n or "product owner" in n or "dono do produto" in n:
                cert = "PO"
            elif " sm" in f" {n} " or "scrum master" in n:
                cert = "SM"
        if cert:
            if "expirad" in n or "vencid" in n:
                return ParsedQuery(kind="people_with_cert_expired", cert_hint=cert)
            return ParsedQuery(kind="people_with_cert_active", cert_hint=cert)

    # person-centric queries
    # detect "vencem este ano" / year
    year = None
    my = _RE_YEAR.search(n)
    if my:
        year = int(my.group(1))
    elif "este ano" in n:
        # resolved in backend as current year
        year = -1

    # pessoa pode aparecer em qualquer lugar:
    # - "certificacoes ativas joao silva"
    # - "certificacoes ativas e lucas paqueta"
    # - "joao silva tem cert ativa"
    # - "quais certificacoes do joao silva vencem este ano"
    person_hint = None
    # "certificações ativas e Lucas Paquetá" (evita capturar "ativas" como nome); `n` = sem acentos
    m_e = re.search(
        r"\b(?:certificacoes|certificacao|certs|certificados|badges|titulos)\b.*?"
        r"\b(?:ativas?|vigentes?|validas?)\s+e\s+([a-zA-Z][a-zA-Z\s\.]{2,})",
        n,
        flags=re.IGNORECASE,
    )
    if m_e:
        person_hint = m_e.group(1).strip()
    if not person_hint:
        m_tail = re.search(
            r"\b(?:certificacoes|certificacao|certs|certificados)\b.*?"
            r"\b(?:ativas?|vigentes?|validas?)\s+([a-zA-Z][a-zA-Z\s\.]{2,})\s*$",
            n.strip(),
            flags=re.IGNORECASE,
        )
        if m_tail:
            person_hint = m_tail.group(1).strip()
    if not person_hint:
        m_de = re.search(r"\b(?:do|da|de)\s+([a-zA-Z][a-zA-Z\s\.]{2,})", n, flags=re.IGNORECASE)
        if m_de:
            person_hint = m_de.group(1).strip()
    if not person_hint:
        m_tem = re.match(r"^\s*([a-zA-Z][a-zA-Z\s\.]{2,})\s+tem\b", n, flags=re.IGNORECASE)
        if m_tem:
            person_hint = m_tem.group(1).strip()
    if not person_hint:
        m_cert = re.search(
            r"\b(?:certificacoes|certificacao|certs|certificados|badges|titulos)\b.*?"
            r"(?:\b(?:ativas?|vigentes?|validas?)\s+e\s+)?"
            r"\b([a-zA-Z][a-zA-Z\s\.]{2,})",
            n,
            flags=re.IGNORECASE,
        )
        if m_cert:
            cand = m_cert.group(1).strip()
            if not re.match(r"^(ativas?|vigentes?|validas?|cert|certs)$", cand, re.IGNORECASE):
                person_hint = cand

    if person_hint:
        if "expirad" in n or "vencid" in n:
            return ParsedQuery(kind="certs_by_person_expired", person_hint=person_hint, year=year)
        if "vencem" in n or "vence" in n:
            return ParsedQuery(kind="certs_by_person_expiring_year", person_hint=person_hint, year=year)
        return ParsedQuery(kind="certs_by_person_active", person_hint=person_hint)

    return None


def best_match_person(person_hint: str, candidates: list[str], *, score_cutoff: int = 80) -> str | None:
    if not candidates:
        return None
    hint_n = normalize_text(person_hint)
    choices = {normalize_text(c): c for c in candidates}
    match = process.extractOne(hint_n, list(choices.keys()), scorer=fuzz.WRatio, score_cutoff=score_cutoff)
    if not match:
        return None
    return choices.get(match[0])

