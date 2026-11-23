import urllib.error
from datetime import datetime

from magstrel import net
from magstrel.models import Job, WorkType
from magstrel.utils import html_to_text

API = "https://api.smartrecruiters.com/v1/companies/{board}/postings"


def fetch(board: str, company: str, known_ids: frozenset[str] = frozenset()) -> list[Job]:
    postings, offset = [], 0
    while True:
        page = net.get_json(API.format(board=board) + f"?limit=100&offset={offset}")
        postings += page["content"]
        offset += len(page["content"])
        if not page["content"] or offset >= page["totalFound"]:
            break
    # the list has no descriptions: fetch each one, but only for postings we don't have yet
    return [
        _to_job(raw, board, company, "" if raw["id"] in known_ids else _description(board, raw["id"]))
        for raw in postings
    ]


def _description(board: str, posting_id: str) -> str:
    try:
        detail = net.get_json(API.format(board=board) + f"/{posting_id}")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ""  # left empty, so the next scrape tries again
    sections = detail.get("jobAd", {}).get("sections", {})
    parts = (sections.get(key, {}).get("text") or "" for key in ("jobDescription", "qualifications", "additionalInformation"))
    return html_to_text("\n".join(parts))


def _to_job(raw: dict, board: str, company: str, description: str) -> Job:
    location = raw.get("location") or {}
    work_type: WorkType | None = "remote" if location.get("remote") else "hybrid" if location.get("hybrid") else None
    return Job(
        raw=raw,
        source="smartrecruiters",
        external_id=raw["id"],
        company=company,
        role=raw["name"].strip(),
        location=location.get("fullLocation") or "",
        official_posting_url=f"https://jobs.smartrecruiters.com/{board}/{raw['id']}",
        description=description,
        published=datetime.fromisoformat(raw["releasedDate"]) if raw.get("releasedDate") else None,
        work_type=work_type,
    )
