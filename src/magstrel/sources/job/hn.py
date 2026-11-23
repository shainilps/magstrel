import html
import re
from datetime import datetime

from magstrel import net
from magstrel.models import Job, WorkType
from magstrel.utils import html_to_text

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=20"
ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"

_CLOSED = re.compile(r"no longer (?:taking|accepting|hiring)|positions? (?:has been |have been )?filled", re.I)
_URL = re.compile(r"^(?:https?://|www\.)\S+$", re.I)
_SALARY = re.compile(r"[$€£₹]\s?\d|\b\d+\s?k\b|/(?:month|year|hour)|\bper (?:year|month|hour)\b|stipend|equity", re.I)
_WORK = re.compile(r"\bremote\b|\bon-?site\b|\bhybrid\b|\bin[- ]office\b", re.I)
_EMPLOYMENT = re.compile(r"^(?:full[- ]?time|part[- ]?time|contract(?:or)?|freelance|internship|ft|pt)\b", re.I)
_ROLE = re.compile(
    r"engineer|developer|designer|scientist|manager|\blead\b|architect|analyst|devops|\bsre\b|\bcto\b|"
    r"head of|founding|market|sales|recruit|research|phd|intern|positions|roles|\bcsm|specialist|"
    r"administrator|technician|writer|product|programmer|\bml\b|\bai\b",
    re.I,
)


def fetch_latest() -> list[tuple[str, Job]]:
    hits = net.get_json(SEARCH_URL)["hits"]
    thread = next((h for h in hits if h["title"].lower().startswith("ask hn: who is hiring")), None)
    if thread is None:
        raise ValueError("couldn't find the latest 'Who is hiring?' thread")
    item = net.get_json(ITEM_URL.format(id=thread["objectID"]), timeout=120)
    posts = (parse_post(comment) for comment in item.get("children") or [])
    return [post for post in posts if post]


def parse_post(comment: dict) -> tuple[str, Job] | None:
    # "Company | Role | Location | REMOTE (worldwide) | Full-time | $150k | https://..."
    text = comment.get("text") or ""
    header = _plain(text.split("<p>")[0])
    if "|" not in header or _CLOSED.search(_plain(text)[:400]):
        return None  # not a job post (a reply-style comment, or the author closed it)

    segments = [s.strip() for s in header.split("|") if s.strip()]
    company = re.sub(r"\s*\([^)]*\)\s*$", "", segments[0]).strip()[:80]
    roles, places, salary = [], [], None
    for segment in segments[1:]:
        if _URL.match(segment) or _EMPLOYMENT.match(segment):
            continue
        if _WORK.search(segment):
            places.append(segment)
        elif _SALARY.search(segment):
            salary = salary or segment[:80]
        elif _ROLE.search(segment) and not roles:
            roles.append(segment)
        elif len(segment) <= 60 and not roles and "," in segment:
            places.append(segment)  # "San Francisco, CA" before any role
        elif len(segment) <= 60 and roles:
            places.append(segment)
    if not company:
        return None

    lowered = header.lower()
    work_type: WorkType | None = (
        "remote" if "remote" in lowered else "hybrid" if "hybrid" in lowered else "in-office" if _WORK.search(lowered) else None
    )
    job = Job(
        raw=comment,
        source="hn",
        external_id=str(comment["id"]),
        company=company,
        role=(roles[0] if roles else "Hiring (see post)")[:150],
        location=" | ".join(places)[:150],
        official_posting_url=_first_link(text) or f"https://news.ycombinator.com/item?id={comment['id']}",
        description=html_to_text(text),
        published=datetime.fromisoformat(comment["created_at"]) if comment.get("created_at") else None,
        work_type=work_type,
        salary=salary,
    )
    return company, job


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(fragment))).strip()


def _first_link(text: str) -> str | None:
    for href in re.findall(r'href="([^"]+)"', text):
        href = html.unescape(href)
        if href.startswith(("http://", "https://")) and "news.ycombinator.com" not in href:
            return href
    return None
