from datetime import datetime


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
