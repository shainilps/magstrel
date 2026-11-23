import re
import urllib.error
from urllib.parse import urlparse

from magstrel import net
from magstrel.sources.job import SOURCES

# a cheap request per ats that answers 404 when the board doesn't exist
# (smartrecruiters answers 200 with zero postings instead, so verification has to catch it)
_PROBE_URLS = {
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json&limit=1",
    "recruitee": "https://{board}.recruitee.com/api/offers/",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{board}/postings?limit=1",
}
# workable is left out of discovery on purpose: it rate-limits (429) after a few dozen quick
# lookups, and an old empty account per company name is common. Add those by hand:
# magstrel company add "X" --ats workable --board x


def find_board(name: str, website: str | None) -> tuple[str, str] | None:
    for board in candidate_boards(name, website):
        for ats, url in _PROBE_URLS.items():
            if _probe(url.format(board=board)) is not None and verify_board(ats, board, name, website) is True:
                return ats, board  # only a confirmed match (True), never "can't tell" (None)
    return None


def verify_board(ats: str, board: str, name: str, website: str | None) -> bool | None:
    # True: its jobs are really this company's. False: they're someone else's.
    # None: no jobs right now, so there's nothing to judge (an empty or abandoned account).
    # stops "Dots" matching a games studio's board, or an old empty account counting as a match
    if ats == "smartrecruiters":
        # every posting carries the company's own name: it must be exactly ours
        page = net.get_json(_PROBE_URLS[ats].format(board=board))
        if not page["totalFound"]:
            return None
        return _squash(page["content"][0]["company"]["name"]) == _squash(name)
    if ats == "greenhouse":
        # greenhouse knows the board owner's name: "agency" belongs to a company called Meridial
        meta = net.get_json(_PROBE_URLS[ats].format(board=board))
        if not _same_name(name, meta.get("name", "")):
            return False
    jobs = SOURCES[ats](board, name)
    if not jobs:
        return None
    if ats == "recruitee":
        # recruitee is full of companies sharing a startup's name (BeGo vs BEGO, a dental firm):
        # require our website's domain in their posting urls or text
        domain = _registrable_domain(website)
        return domain is not None and any(
            domain in job.official_posting_url.lower() or domain in job.description.lower() for job in jobs
        )
    return any(_mentions(job.description, name, website) for job in jobs)


def candidate_boards(name: str, website: str | None) -> list[str]:
    lowered = name.lower()
    candidates = [re.sub(r"[^a-z0-9]", "", lowered)]
    domain = _domain_label(website)
    if domain:
        candidates.append(domain)
    candidates.append(re.sub(r"[^a-z0-9]+", "-", lowered).strip("-"))
    return list(dict.fromkeys(c for c in candidates if c))


def _probe(url: str) -> dict | list | None:
    try:
        return net.get_json(url, timeout=15)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def _mentions(text: str, name: str, website: str | None) -> bool:
    # whole words only ("Alex" must not match "Dentalex"), and the name with its own
    # capitals: a company writes "Agency", while job text says "agency" as a plain word
    name = re.sub(r"[^\w\s]", "", name).strip()
    domain = _domain_label(website)
    return bool(
        (len(name) >= 3 and re.search(rf"\b{re.escape(name)}\b", text))
        or (len(domain) >= 3 and re.search(rf"\b{re.escape(domain)}\b", text, re.I))
    )


def _registrable_domain(website: str | None) -> str | None:
    host = (urlparse(website).hostname or "") if website else ""
    parts = host.lower().removeprefix("www.").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else None


def _domain_label(website: str | None) -> str:
    host = (urlparse(website).hostname or "") if website else ""
    return _squash(host.removeprefix("www.").split(".")[0])


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _same_name(a: str, b: str) -> bool:
    a, b = _squash(a), _squash(b)
    return bool(a and b) and (a in b or b in a)
