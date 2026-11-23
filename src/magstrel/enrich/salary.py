import re

_AMOUNT = r"(\d{2,3}(?:,\d{3})+(?:\.\d{2})?|\d{2,3}(?:\.\d+)?\s?[kK])"
# needs "k" or a thousands separator, so hourly rates like "$50 - $70" don't match
_PATTERN = re.compile(rf"([$£€])\s?{_AMOUNT}\s*(?:-|–|—|to)\s*(?:[$£€]\s?)?{_AMOUNT}")


def salary(description: str) -> str | None:
    for match in _PATTERN.finditer(description):
        currency, low, high = match[1], _thousands(match[2]), _thousands(match[3])
        if 10 <= low <= high:
            return f"{currency}{_fmt(low)}K - {currency}{_fmt(high)}K"
    return None


def _thousands(text: str) -> float:
    text = text.replace(" ", "")
    if text[-1] in "kK":
        return float(text[:-1])
    return float(text.replace(",", "")) / 1000


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:g}"
