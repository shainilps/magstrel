import html
import json
import re
import threading
import time
import urllib.error
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

from magstrel import net
from magstrel.models import Job

BASE_URL = "https://www.ycombinator.com"

MIN_INTERVAL = 1.0
_lock = threading.Lock()
_next_request_at = 0.0

_UNIT_DAYS = {
    "minute": 1 / 1440,
    "hour": 1 / 24,
    "day": 1,
    "week": 7,
    "month": 30,
    "year": 365,
}


def fetch(
    board: str, company: str, known_ids: frozenset[str] = frozenset()
) -> list[Job]:
    props = _page_props(f"{BASE_URL}/companies/{board}/jobs")
    contacts = _founder_contacts(props.get("company") or {})
    jobs = []
    for raw in props["jobPostings"]:
        external_id = str(raw["id"])
        description = "" if external_id in known_ids else _description(raw["url"])
        jobs.append(_to_job(raw, company, description, contacts))
    return jobs


def _founder_contacts(company: dict) -> dict[str, str]:
    contacts = {}
    for founder in company.get("founders") or []:
        if not founder.get("is_active", True) or not founder.get("full_name"):
            continue
        who = founder["full_name"]
        if founder.get("title"):
            who += f" ({founder['title']})"
        contacts[who] = founder.get("linkedin_url") or founder.get("twitter_url") or ""
    return contacts


def _to_job(raw: dict, company: str, description: str, contacts: dict[str, str]) -> Job:
    location = raw.get("location") or ""
    return Job(
        raw=raw,
        source="yc",
        external_id=str(raw["id"]),
        company=company,
        role=raw["title"].strip(),
        location=location,
        official_posting_url=BASE_URL + raw["url"],
        description=description,
        published=_approx_date(raw.get("createdAt") or ""),
        work_type="remote" if "remote" in location.lower() else None,
        min_loe=_min_years(raw.get("minExperience") or ""),
        skills=[
            s["name"] if isinstance(s, dict) else str(s)
            for s in raw.get("skills") or []
        ],
        salary=raw.get("salaryRange") or None,
        equity=raw.get("equityRange") or None,
        visa=raw.get("visa") or None,
        recruiter_detail=contacts,
    )


def _description(path: str) -> str:
    try:
        return html.unescape(_page_props(BASE_URL + path)["job"].get("description") or "")
    except urllib.error.URLError, TimeoutError, ValueError, KeyError:
        return ""


def _page_props(url: str) -> dict:
    parser = _DataPageParser()
    parser.feed(_get_text(url))
    if parser.data_page is None:
        raise ValueError(f"YC page format changed: no data-page on {url}")
    return json.loads(parser.data_page)["props"]


def _get_text(url: str) -> str:
    for attempt in range(1, 4):
        _wait_turn()
        try:
            return net.get_text(url)
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == 3:
                raise
            _pause_all(30 * attempt)
    raise AssertionError("unreachable")


def _wait_turn() -> None:
    global _next_request_at
    with _lock:
        now = time.monotonic()
        slot = max(now, _next_request_at)
        _next_request_at = slot + MIN_INTERVAL
    time.sleep(slot - now)


def _pause_all(seconds: float) -> None:
    global _next_request_at
    with _lock:
        _next_request_at = max(_next_request_at, time.monotonic() + seconds)


class _DataPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.data_page: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.data_page is not None:
            return
        for name, value in attrs:
            if name == "data-page" and value:
                self.data_page = value


def _approx_date(created_at: str) -> datetime | None:
    match = re.search(r"(\d+|an?)\s+(minute|hour|day|week|month|year)", created_at)
    if not match:
        return None
    amount = 1 if match[1] in ("a", "an") else int(match[1])
    return datetime.now(UTC) - timedelta(days=amount * _UNIT_DAYS[match[2]])


def _min_years(text: str) -> int | None:
    if match := re.search(r"(\d+)", text):
        return int(match[1])
    if "new grad" in text.lower() or text.lower().startswith("any"):
        return 0
    return None
