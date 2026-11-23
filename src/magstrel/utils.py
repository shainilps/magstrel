from datetime import UTC, datetime


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
