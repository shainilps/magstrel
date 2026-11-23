import re

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUM = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)"
_YEARS = r"(?:years?|yrs?)"

# one combined pattern, so the FIRST mention in the text wins whatever its shape
_PATTERN = re.compile(
    "|".join([
        rf"(?P<lo>{_NUM})\s*(?:-|–|—|to)\s*(?P<hi>{_NUM})\s*\+?\s*{_YEARS}",           # 3-5 years
        rf"(?P<plus>{_NUM})\s*\+\s*{_YEARS}",                                       # 5+ years
        rf"(?:at least|minimum(?: of)?|min\.?)\s*(?P<least>{_NUM})\s*\+?\s*{_YEARS}",  # at least 4 years
        rf"(?P<bare>{_NUM})\s*{_YEARS}(?:['’]s?)?\s+(?:of\s+)?(?:[\w-]+[\s,/&]+){{0,4}}?experience",  # 3 years of python experience
    ]),
    re.I,
)


def years(description: str) -> tuple[int | None, int | None]:
    for match in _PATTERN.finditer(description):
        if match["lo"]:
            low, high = _number(match["lo"]), _number(match["hi"])
            if low <= high <= 20:
                return low, high
            continue
        value = _number(match["plus"] or match["least"] or match["bare"])
        if value <= 20:  # more is "20 years in business", not a requirement
            return value, None
    return None, None


def _number(text: str) -> int:
    return int(text) if text.isdigit() else _WORDS[text.lower()]
