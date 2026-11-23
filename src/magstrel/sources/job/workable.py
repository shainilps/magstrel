from datetime import UTC, datetime

from magstrel import net
from magstrel.models import Job
from magstrel.utils import html_to_text


def fetch(board: str, company: str) -> list[Job]:
    data = net.get_json(f"https://apply.workable.com/api/v1/widget/accounts/{board}?details=true")
    return [_to_job(raw, company) for raw in data.get("jobs") or []]


def _to_job(raw: dict, company: str) -> Job:
    place = (raw.get("locations") or [{}])[0]
    location = ", ".join(
        part for part in (place.get("city") or raw.get("city"), place.get("country") or raw.get("country")) if part
    )
    published = raw.get("published_on")  # "2026-08-04"
    return Job(
        raw=raw,
        source="workable",
        external_id=raw["shortcode"],
        company=company,
        role=raw["title"].strip(),
        location=location,
        official_posting_url=raw["url"],
        description=html_to_text(raw.get("description") or ""),
        published=datetime.fromisoformat(published).replace(tzinfo=UTC) if published else None,
        work_type="remote" if raw.get("telecommuting") else None,
    )
