"""Compatibilidade: delega detecção de intenção para `nlp.parse_query`."""
from __future__ import annotations

# Mantido por compatibilidade; a detecção principal agora está em `nlp.py`.

from dataclasses import dataclass

from searchCertSystem.api.nlp import ParsedQuery, parse_query


@dataclass(frozen=True)
class Intent:
    kind: str
    value: str


def detect_intent(message: str) -> Intent | None:
    pq: ParsedQuery | None = parse_query(message)
    if not pq:
        return None
    # API antiga esperava "kind" + "value"
    value = pq.person_hint or pq.cert_hint or ""
    return Intent(kind=pq.kind, value=value)

