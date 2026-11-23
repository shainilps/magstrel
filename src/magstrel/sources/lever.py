from datetime import UTC, datetime

from magstrel import net
from magstrel.models import Job, WorkType

_WORK_TYPES: dict[str, WorkType] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "in-office",
}


def fetch(board: str, company: str) -> list[Job]:
    data = net.get_json(f"https://api.lever.co/v0/postings/{board}?mode=json")
    return [_to_job(raw, company) for raw in data]


def _to_job(raw: dict, company: str) -> Job:
    created_ms = raw.get("createdAt")
    categories = raw.get("categories") or {}
    return Job(
        raw=raw,
        source="lever",
        external_id=raw["id"],
        company=company,
        role=raw["text"].strip(),
        location=categories.get("location") or "",
        official_posting_url=raw["hostedUrl"],
        description=raw.get("descriptionPlain") or "",
        published=datetime.fromtimestamp(created_ms / 1000, UTC)
        if created_ms
        else None,
        work_type=_WORK_TYPES.get(raw.get("workplaceType") or ""),
    )
