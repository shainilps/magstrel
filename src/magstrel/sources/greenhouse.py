import json
import urllib.error
import urllib.request
from datetime import datetime

from magstrel.models import Job


def fetch(board: str) -> list[Job]:
    req = urllib.request.Request(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
        headers={"User-Agent": "magstrel/0.1"},
    )
    raw_jobs = []
    try:
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
            raw_jobs = data["jobs"]
    except urllib.error.HTTPError as err:
        print(f"server error: {err.code}")
    except urllib.error.URLError as err:
        print(f"network problem: {err.reason}")

    return [_to_job(raw) for raw in raw_jobs]


def _to_job(raw: dict) -> Job:
    published = raw.get("first_published") or raw.get("updated_at")
    return Job(
        source="greenhouse",
        external_id=str(raw["id"]),
        company=raw.get("company_name") or "",
        role=raw["title"].strip(),
        location=(raw.get("location") or {}).get("name", ""),
        official_posting_url=raw["absolute_url"],
        published=datetime.fromisoformat(published) if published else None,
    )
