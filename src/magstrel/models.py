from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

WorkType = Literal["remote", "hybrid", "in-office"]
CompanyType = Literal["startup", "midsize", "bigtech"]


@dataclass
class Company:
    name: str

    ats: str | None = None
    board: str | None = None

    website: str | None = None
    career_site: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    employees_min: int | None = None
    employees_max: int | None = None
    company_type: CompanyType | None = None

    id: int | None = None


@dataclass(frozen=True)
class ScrapeTarget:
    company_id: int
    name: str
    ats: str
    board: str


@dataclass
class SearchQuery:
    terms: list[str] = field(default_factory=list)
    raw: bool = False
    work_type: WorkType | None = None
    company_type: CompanyType | None = None
    tag: str | None = None
    company: str | None = None
    location: str | None = None
    max_employees: int | None = None
    days: int | None = None
    limit: int = 30


@dataclass
class Job:
    raw: dict[str, Any] = field(repr=False, compare=False)
    source: str
    external_id: str
    company: str
    role: str
    location: str
    official_posting_url: str

    description: str = field(default="", repr=False)
    published: datetime | None = None
    deadline: datetime | None = None

    work_type: WorkType | None = None
    min_loe: int | None = None
    max_loe: int | None = None
    skills: list[str] = field(default_factory=list)
    recruiter_detail: dict[str, str] = field(default_factory=dict)
