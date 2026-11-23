import re

from magstrel.models import Seniority

# first match wins: "Director, Staff Engineering" is a director
_RULES: list[tuple[Seniority, re.Pattern[str]]] = [
    ("intern", re.compile(r"\bintern(ship)?\b|\bco-?op\b", re.I)),
    ("director", re.compile(r"\b(director|vp|vice president|head of|chief|cto|ceo|cfo|coo)\b", re.I)),
    ("principal", re.compile(r"\b(principal|distinguished|fellow)\b", re.I)),
    ("staff", re.compile(r"\bstaff\b", re.I)),
    ("manager", re.compile(r"\b(engineering|software|development|technical) manager\b|\bmanager,? engineering\b", re.I)),
    ("lead", re.compile(r"\b(tech )?lead\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr|entry[- ]level|new grad(uate)?|graduate|associate)\b", re.I)),
    ("mid", re.compile(r"\bmid[- ]level\b", re.I)),
    # roman numeral levels are case-sensitive, or the "i" in ordinary words would match
    ("senior", re.compile(r"\b(III|IV)\b")),
    ("mid", re.compile(r"\bII\b")),
    ("junior", re.compile(r"\bI$")),
]


def seniority(title: str) -> Seniority | None:
    for level, pattern in _RULES:
        if pattern.search(title):
            return level
    return None
