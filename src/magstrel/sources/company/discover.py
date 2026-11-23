import re
import urllib.error
from urllib.parse import urlparse

from magstrel import net

_PROBE_URLS = {
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json&limit=1",
}


def find_board(name: str, website: str | None) -> tuple[str, str] | None:
    for board in candidate_boards(name, website):
        for ats, url in _PROBE_URLS.items():
            data = _probe(url.format(board=board))
            if data is None:
                continue
            if ats == "greenhouse":
                board_name = data.get("name", "") if isinstance(data, dict) else ""
                if not _same_name(name, board_name):
                    continue
            return ats, board
    return None


def candidate_boards(name: str, website: str | None) -> list[str]:
    lowered = name.lower()
    candidates = [re.sub(r"[^a-z0-9]", "", lowered)]
    if website:
        host = (urlparse(website).hostname or "").removeprefix("www.")
        candidates.append(host.split(".")[0])
    candidates.append(re.sub(r"[^a-z0-9]+", "-", lowered).strip("-"))
    return list(dict.fromkeys(c for c in candidates if c))


def _probe(url: str) -> dict | list | None:
    try:
        return net.get_json(url, timeout=15)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def _same_name(a: str, b: str) -> bool:
    a, b = re.sub(r"[^a-z0-9]", "", a.lower()), re.sub(r"[^a-z0-9]", "", b.lower())
    return bool(a and b) and (a in b or b in a)
