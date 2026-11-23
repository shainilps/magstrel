import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any, get_args

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from magstrel import db
from magstrel.models import Category, CompanyType, SearchQuery, Seniority
from magstrel.utils import age, format_employees

app = FastAPI(title="magstrel")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["age"] = age


def _safe_url(url: str | None) -> str:
    return url if url and url.startswith(("https://", "http://")) else "#"


templates.env.filters["safe_url"] = _safe_url


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


@app.get("/", response_class=HTMLResponse)
def search_page(
    request: Request,
    conn: Conn,
    q: str = "",
    remote: bool = False,
    seniority: str = "",
    category: str = "",
    company_type: str = "",
    skill: str = "",
    tag: str = "",
    location: str = "",
    years: str = "",
    days: str = "",
    closed: bool = False,
) -> HTMLResponse:
    query = SearchQuery(
        terms=q.split(),
        work_type="remote" if remote else None,
        seniority=_choice(seniority, Seniority),
        category=_choice(category, Category),
        company_type=_choice(company_type, CompanyType),
        skill=skill.strip() or None,
        tag=tag.strip() or None,
        location=location.strip() or None,
        years=_number(years),
        days=_number(days),
        include_closed=closed,
        limit=100,
    )
    error = None
    try:
        jobs = db.search_jobs(conn, query)
    except sqlite3.OperationalError as err:
        jobs, error = [], f"bad search: {err}"

    form = {
        "q": q,
        "remote": remote,
        "seniority": seniority,
        "category": category,
        "company_type": company_type,
        "skill": skill,
        "tag": tag,
        "location": location,
        "years": years,
        "days": days,
        "closed": closed,
    }
    options = {
        "seniority": get_args(Seniority),
        "category": get_args(Category),
        "company_type": get_args(CompanyType),
    }
    return templates.TemplateResponse(
        request,
        "search.html",
        {"jobs": jobs, "form": form, "options": options, "error": error},
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: int, conn: Conn) -> HTMLResponse:
    job = db.get_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no such job")
    context: dict[str, Any] = {
        "job": job,
        "tags": json.loads(job["tags"]),
        "skills": json.loads(job["skills"]),
        "contacts": json.loads(job["recruiter_detail"]),
        "employees": format_employees(job["employees_min"], job["employees_max"]),
    }
    return templates.TemplateResponse(request, "job.html", context)


def _choice(value: str, allowed: Any) -> Any:
    return value if value in get_args(allowed) else None


def _number(text: str) -> int | None:
    return int(text) if text.strip().isdigit() else None
