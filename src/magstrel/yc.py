import re

from magstrel import net
from magstrel.models import Company, CompanyType

YC_COMPANIES_URL = "https://yc-oss.github.io/api/companies/all.json"

_SEASONS = {"Winter": "w", "Summer": "s", "Spring": "x", "Fall": "f"}


def fetch_companies(include_all: bool = False) -> list[Company]:
    data = net.get_json(YC_COMPANIES_URL, timeout=120)
    return [
        _to_company(raw)
        for raw in data
        if include_all or (raw.get("status") == "Active" and raw.get("isHiring"))
    ]


def _to_company(raw: dict) -> Company:
    team_size = raw.get("team_size") or None
    tags = ["yc-backed"]
    if batch_tag := _batch_tag(raw.get("batch") or ""):
        tags.append(batch_tag)
    for tag in [*(raw.get("industries") or []), *(raw.get("tags") or [])]:
        slug = _slug(tag)
        if slug and slug not in tags:
            tags.append(slug)
    return Company(
        name=raw["name"].strip(),
        website=raw.get("website") or None,
        description=raw.get("one_liner") or "",
        tags=tags,
        employees_min=team_size,
        employees_max=team_size,
        company_type=_company_type(team_size),
    )


def _batch_tag(batch: str) -> str | None:
    match = re.fullmatch(r"(\w+) (\d{4})", batch)
    if not match or match[1] not in _SEASONS:
        return None
    return f"yc-{_SEASONS[match[1]]}{match[2][-2:]}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _company_type(team_size: int | None) -> CompanyType | None:
    if team_size is None:
        return None
    if team_size < 200:
        return "startup"
    if team_size < 5000:
        return "midsize"
    return "bigtech"
