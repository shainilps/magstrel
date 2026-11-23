from datetime import UTC, datetime

from magstrel import net
from magstrel.models import Job
from magstrel.utils import html_to_text


def fetch(board: str, company: str) -> list[Job]:
    data = net.get_json(f"https://{board}.recruitee.com/api/offers/")
    return [_to_job(raw, company) for raw in data["offers"]]


def _to_job(raw: dict, company: str) -> Job:
    published = raw.get("published_at")  # "2026-11-18 16:23:32 UTC"
    return Job(
        raw=raw,
        source="recruitee",
        external_id=str(raw["id"]),
        company=company,
        role=raw["title"].strip(),
        location=raw.get("location") or "",
        official_posting_url=raw["careers_url"],
        description=html_to_text(f"{raw.get('description') or ''}\n{raw.get('requirements') or ''}"),
        published=datetime.strptime(published, "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=UTC)
        if published
        else None,
        work_type="remote" if raw.get("remote") else None,
        salary=_salary(raw.get("salary") or {}),
    )


def _salary(salary: dict) -> str | None:
    if not salary.get("min"):
        return None
    period = f" per {salary['period']}" if salary.get("period") else ""
    return f"{salary['min']}-{salary.get('max') or salary['min']} {salary.get('currency') or ''}{period}".strip()
