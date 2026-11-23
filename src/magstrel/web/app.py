import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, get_args

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from magstrel import db, mcp_server
from magstrel.models import Category, CompanyType, SearchQuery, Seniority
from magstrel.scheduler import Refresher
from magstrel.utils import age, format_employees, until


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # app.state.refresh_every is set by `magstrel server` before uvicorn starts the app
    every = getattr(app.state, "refresh_every", None)
    app.state.refresher = Refresher(every) if every else None
    if app.state.refresher:
        app.state.refresher.start()
    async with mcp_server.server.session_manager.run():
        yield
    if app.state.refresher:
        app.state.refresher.stop()


app = FastAPI(title="magstrel", lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["age"] = age
templates.env.filters["until"] = until


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
    context = {
        "jobs": jobs,
        "form": form,
        "options": options,
        "error": error,
        "state": db.get_state(conn),
        "refresher_on": request.app.state.refresher is not None,
    }
    return templates.TemplateResponse(request, "search.html", context)


@app.post("/refresh")
def refresh_now(request: Request) -> RedirectResponse:
    if request.app.state.refresher:
        request.app.state.refresher.trigger()
    return RedirectResponse("/", status_code=303)


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


app.router.routes.extend(mcp_server.server.streamable_http_app().routes)
