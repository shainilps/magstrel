from collections.abc import Callable

from magstrel.models import Job
from magstrel.sources.job import ashby, greenhouse, lever, recruitee, smartrecruiters, workable

# the job board systems (ATSs) a company can be linked to; "yc" is a fallback, not listed here
SOURCES: dict[str, Callable[[str, str], list[Job]]] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "recruitee": recruitee.fetch,
    "workable": workable.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}
