from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class Job:
    raw: dict[str, Any] = field(repr=False, compare=False)
    source: str
    external_id: str
    company: str
    role: str
    location: str
    official_posting_url: str

    description: str = ""
    published: datetime | None = None
    deadline: datetime | None = None

    work_type: Literal["remote", "hybrid", "in-office"] | None = None
    min_loe: int | None = None
    max_loe: int | None = None
    company_type: Literal["startup", "midsize", "bigtech"] | None = None
    skills: list[str] = field(default_factory=list)
    # e.g. "yc-backed", "open-source"
    meta: list[str] = field(default_factory=list)
    # email, phone number, linkedin, or any other way to contact
    recruiter_detail: dict[str, str] = field(default_factory=dict)
