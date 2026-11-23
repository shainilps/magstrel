from datetime import datetime

from magstrel import net
from magstrel.models import Job, WorkType

_WORK_TYPES: dict[str, WorkType] = {
    "Remote": "remote",
    "Hybrid": "hybrid",
    "OnSite": "in-office",
}


def fetch(board: str, company: str) -> list[Job]:
    data = net.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true")
    return [_to_job(raw, company) for raw in data["jobs"] if raw.get("isListed", True)]


def _to_job(raw: dict, company: str) -> Job:
    published = raw.get("publishedAt")
    compensation = raw.get("compensation") or {}
    tiers = compensation.get("compensationTierSummary") or ""
    work_type = _WORK_TYPES.get(raw.get("workplaceType") or "")
    if work_type is None and raw.get("isRemote"):
        work_type = "remote"
    return Job(
        raw=raw,
        source="ashby",
        external_id=raw["id"],
        company=company,
        role=raw["title"].strip(),
        location=raw.get("location") or "",
        official_posting_url=raw["jobUrl"],
        description=raw.get("descriptionPlain") or "",
        published=datetime.fromisoformat(published) if published else None,
        work_type=work_type,
        salary=compensation.get("scrapeableCompensationSalarySummary") or None,
        equity="offers equity" if "equity" in tiers.lower() else None,
    )
