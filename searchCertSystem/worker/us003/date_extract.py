from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


_DATE_DMY = re.compile(r"\b(?P<d>\d{1,2})[\/\-\.](?P<m>\d{1,2})[\/\-\.](?P<y>\d{2,4})\b")
_DATE_YMD = re.compile(r"\b(?P<y>\d{4})[\/\-\.](?P<m>\d{1,2})[\/\-\.](?P<d>\d{1,2})\b")

_MONTHS = {
    # PT
    "jan": 1,
    "janeiro": 1,
    "fev": 2,
    "fevereiro": 2,
    "mar": 3,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "abr": 4,
    "mai": 5,
    "maio": 5,
    "jun": 6,
    "junho": 6,
    "jul": 7,
    "julho": 7,
    "ago": 8,
    "agosto": 8,
    "set": 9,
    "setembro": 9,
    "out": 10,
    "outubro": 10,
    "nov": 11,
    "novembro": 11,
    "dez": 12,
    "dezembro": 12,
    # EN
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_DATE_TEXTUAL = re.compile(
    r"\b(?P<d>\d{1,2})\s*(de\s*)?(?P<mon>[A-Za-zçÇ]+)\s*(de\s*)?(?P<y>\d{4})\b",
    re.IGNORECASE,
)

# EN textual: January 15, 2024  /  Jan 15 2024
_DATE_TEXTUAL_MDY = re.compile(
    r"\b(?P<mon>[A-Za-z]+)\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?\,?\s+(?P<y>\d{4})\b",
    re.IGNORECASE,
)

# EN textual: 15 January 2024  /  15 Jan 2024
_DATE_TEXTUAL_DMY = re.compile(
    r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<mon>[A-Za-z]+)\.?\s+(?P<y>\d{4})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedDates:
    issue_date: date | None
    expiry_date: date | None
    evidence_issue: str | None
    evidence_expiry: str | None

    def to_json(self) -> dict[str, str | None]:
        def br(d: date | None) -> str | None:
            return d.strftime("%d/%m/%Y") if d else None

        return {
            # Formato brasileiro para consumo humano
            "issue_date": br(self.issue_date),
            "expiry_date": br(self.expiry_date),
            # ISO para integrações (Supabase, etc.)
            "issue_date_iso": self.issue_date.isoformat() if self.issue_date else None,
            "expiry_date_iso": self.expiry_date.isoformat() if self.expiry_date else None,
            "evidence_issue": self.evidence_issue,
            "evidence_expiry": self.evidence_expiry,
        }


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _normalize_year(y: int) -> int:
    if y < 100:
        return 2000 + y if y <= 50 else 1900 + y
    return y


def _parse_any_date(token: str) -> date | None:
    token = token.strip()
    m = _DATE_YMD.search(token)
    if m:
        y = int(m.group("y"))
        mo = int(m.group("m"))
        d = int(m.group("d"))
        return _safe_date(y, mo, d)

    m = _DATE_DMY.search(token)
    if m:
        d = int(m.group("d"))
        mo = int(m.group("m"))
        y = _normalize_year(int(m.group("y")))
        return _safe_date(y, mo, d)

    m = _DATE_TEXTUAL.search(token)
    if m:
        d = int(m.group("d"))
        mon_raw = m.group("mon").strip().lower()
        mon_raw = mon_raw.replace(".", "")
        mo = _MONTHS.get(mon_raw)
        if not mo:
            return None
        y = int(m.group("y"))
        return _safe_date(y, mo, d)

    m = _DATE_TEXTUAL_MDY.search(token)
    if m:
        mon_raw = m.group("mon").strip().lower().replace(".", "")
        mo = _MONTHS.get(mon_raw)
        if not mo:
            return None
        d = int(m.group("d"))
        y = int(m.group("y"))
        return _safe_date(y, mo, d)

    m = _DATE_TEXTUAL_DMY.search(token)
    if m:
        mon_raw = m.group("mon").strip().lower().replace(".", "")
        mo = _MONTHS.get(mon_raw)
        if not mo:
            return None
        d = int(m.group("d"))
        y = int(m.group("y"))
        return _safe_date(y, mo, d)

    return None


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _find_best_date_near_keywords(text: str, keywords: list[str]) -> tuple[date | None, str | None]:
    text_norm = text
    lower = text_norm.lower()

    best: tuple[int, date, str] | None = None
    window = 160  # chars after keyword

    for kw in keywords:
        start = 0
        while True:
            idx = lower.find(kw, start)
            if idx == -1:
                break
            snippet = text_norm[idx : idx + len(kw) + window]
            snip_compact = _compact(snippet)

            # procurar primeiro a data dentro do snippet
            candidates: list[tuple[date, str]] = []
            for rx in (_DATE_YMD, _DATE_DMY, _DATE_TEXTUAL, _DATE_TEXTUAL_MDY, _DATE_TEXTUAL_DMY):
                for m in rx.finditer(snippet):
                    token = m.group(0)
                    dt = _parse_any_date(token)
                    if dt:
                        candidates.append((dt, token))
            if candidates:
                # escolhe a primeira encontrada (mais próxima do keyword)
                dt, token = candidates[0]
                score = idx  # menor idx é "melhor" (aparece mais cedo no doc)
                evidence = f"{kw}: {snip_compact}"
                if best is None or score < best[0]:
                    best = (score, dt, evidence)

            start = idx + len(kw)

    if not best:
        return None, None
    return best[1], best[2]


def extract_issue_and_expiry_dates(text: str) -> ExtractedDates:
    issue_keywords = [
        "emitido em",
        "emissão",
        "data de emissão",
        "issued on",
        "issue date",
        "issued:",
    ]
    expiry_keywords = [
        "válido até",
        "validade",
        "data de validade",
        "expires on",
        "expiration",
        "expiry date",
        "valid until",
        "expires:",
    ]

    issue_dt, issue_ev = _find_best_date_near_keywords(text, issue_keywords)
    expiry_dt, expiry_ev = _find_best_date_near_keywords(text, expiry_keywords)

    # Heurística fallback (sem keywords):
    # - data mais antiga = emissão
    # - data mais futura = validade
    if not issue_dt or not expiry_dt:
        dates: list[date] = []
        for rx in (_DATE_YMD, _DATE_DMY, _DATE_TEXTUAL, _DATE_TEXTUAL_MDY, _DATE_TEXTUAL_DMY):
            for m in rx.finditer(text):
                dt = _parse_any_date(m.group(0))
                if dt:
                    dates.append(dt)
            if len(dates) >= 2:
                break
        dates = sorted(set(dates))
        if dates:
            oldest = dates[0]
            newest = dates[-1]

            if not issue_dt:
                issue_dt = oldest
                issue_ev = "heurística: data mais antiga encontrada (emissão)"

            if not expiry_dt and len(dates) >= 2:
                expiry_dt = newest
                expiry_ev = "heurística: data mais futura encontrada (validade)"

    return ExtractedDates(
        issue_date=issue_dt,
        expiry_date=expiry_dt,
        evidence_issue=issue_ev,
        evidence_expiry=expiry_ev,
    )

