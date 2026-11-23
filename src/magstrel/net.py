import json
import urllib.request
from typing import Any

USER_AGENT = "magstrel/0.1"


def get_json(url: str, timeout: float = 30) -> Any:
    """GET a URL and parse the JSON body. Raises on HTTP or network errors."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)
