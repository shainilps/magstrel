import hashlib

from magstrel.enrich.category import category
from magstrel.enrich.experience import years
from magstrel.enrich.salary import salary
from magstrel.enrich.seniority import seniority
from magstrel.enrich.skills import skills
from magstrel.enrich.visa import visa
from magstrel.enrich.work_type import work_type
from magstrel.models import Enrichment

METHOD = "rules"
# bump this whenever a rule changes: `magstrel enrich` then redoes every job
VERSION = 1


def enrich(title: str, location: str, description: str) -> Enrichment:
    min_loe, max_loe = years(description)
    return Enrichment(
        work_type=work_type(title, location, description),
        min_loe=min_loe,
        max_loe=max_loe,
        salary=salary(description),
        visa=visa(description),
        skills=skills(title, description),
        seniority=seniority(title),
        category=category(title),
    )


def input_hash(title: str, location: str, description: str) -> str:
    return hashlib.sha256(f"{title}\n{location}\n{description}".encode()).hexdigest()[:16]
