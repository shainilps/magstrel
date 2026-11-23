from datetime import datetime

from magstrel import net
from magstrel.models import Job


def fetch(board: str, company: str) -> list[Job]:
    data = net.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
    return [_to_job(raw, company) for raw in data["jobs"]]


def _to_job(raw: dict, company: str) -> Job:
    published = raw.get("first_published") or raw.get("updated_at")
    return Job(
        raw=raw,
        source="greenhouse",
        external_id=str(raw["id"]),
        company=raw.get("company_name") or company,
        role=raw["title"].strip(),
        location=(raw.get("location") or {}).get("name", ""),
        official_posting_url=raw["absolute_url"],
        published=datetime.fromisoformat(published) if published else None,
    )
