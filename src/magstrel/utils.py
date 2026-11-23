import re
from datetime import UTC, datetime
from html.parser import HTMLParser


def parse_employees(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    try:
        if text.endswith("+"):
            return int(text[:-1]), None
        if "-" in text:
            low, high = text.split("-", 1)
            return int(low), int(high)
        return int(text), int(text)
    except ValueError:
        raise ValueError(f"can't read employees {text!r}, use e.g. 50-200, 5000+ or 120") from None


def parse_csv(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def age(iso: str | None) -> str:
    if not iso:
        return "?"
    seconds = (datetime.now(UTC) - datetime.fromisoformat(iso)).total_seconds()
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    if seconds < 86400 * 365:
        return f"{int(seconds // 86400)}d"
    return f"{int(seconds // (86400 * 365))}y"


def format_employees(low: int | None, high: int | None) -> str:
    if low is None and high is None:
        return "size unknown"
    if low == high:
        return f"{low} employees"
    if high is None:
        return f"{low}+ employees"
    return f"{low}-{high} employees"


def cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class _TextParser(HTMLParser):
    _BLOCKS = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "tr", "section"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
