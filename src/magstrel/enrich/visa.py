import re

_NO = re.compile(
    r"\b(unable|not able|cannot|can't|can not|do not|don't|does not|doesn't|will not|won't|are not|is not)\s+"
    r"(?:to\s+)?(?:currently\s+)?(?:offer|provide|support|sponsor)\w*\s+(?:\w+\s+){0,3}?"
    r"(?:visa|sponsorship|work authori[sz]ation)"
    r"|\bno (?:visa )?sponsorship\b"
    r"|\bsponsorship (?:is )?not (?:available|offered|provided)\b",
    re.I,
)
_YES = re.compile(
    r"\b(?:visa )?sponsorship (?:is )?(?:available|offered|provided)\b"
    r"|\b(?:we|will|can|able to)\s+(?:offer\s+|provide\s+)?(?:visa\s+)?sponsor"
    r"|\bsponsor (?:work )?visas?\b"
    r"|\bh-?1b (?:sponsorship|transfer)",
    re.I,
)


def visa(description: str) -> str | None:
    # check "no" first: "we are not able to sponsor" also contains "able to sponsor"
    if _NO.search(description):
        return "no sponsorship"
    if _YES.search(description):
        return "sponsors visa"
    return None
