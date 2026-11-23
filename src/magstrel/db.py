import json
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from magstrel.models import Company, Enrichment, Job, ScrapeTarget, SearchQuery
from magstrel.utils import to_iso

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

UPSERT = """
INSERT INTO jobs (
    company_id, source, external_id, company, role, location, official_posting_url,
    description, published, deadline, work_type, min_loe, skills,
    salary, equity, visa, recruiter_detail, raw, first_seen, last_seen
) VALUES (
    :company_id, :source, :external_id, :company, :role, :location, :official_posting_url,
    :description, :published, :deadline, :work_type, :min_loe, :skills,
    :salary, :equity, :visa, :recruiter_detail, :raw, :now, :now
)
ON CONFLICT (source, external_id) DO UPDATE SET
    company_id           = excluded.company_id,
    company              = excluded.company,
    role                 = excluded.role,
    location             = excluded.location,
    official_posting_url = excluded.official_posting_url,
    description          = COALESCE(NULLIF(excluded.description, ''), jobs.description),
    published            = excluded.published,
    deadline             = excluded.deadline,
    work_type            = COALESCE(excluded.work_type, jobs.work_type),
    min_loe              = COALESCE(excluded.min_loe, jobs.min_loe),
    skills               = CASE WHEN excluded.skills <> '[]' THEN excluded.skills ELSE jobs.skills END,
    salary               = excluded.salary,
    equity               = excluded.equity,
    visa                 = excluded.visa,
    recruiter_detail     = CASE WHEN excluded.recruiter_detail <> '{}'
                                THEN excluded.recruiter_detail ELSE jobs.recruiter_detail END,
    raw                  = excluded.raw,
    last_seen            = excluded.last_seen,
    closed_at            = NULL
RETURNING first_seen = last_seen AS is_new
"""


def path() -> Path:
    return Path(os.environ.get("MAGSTREL_DB", "jobs.db")).resolve()


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    # timeout: wait up to 30s for another writer (the background refresher) instead of failing
    conn = sqlite3.connect(db_path or path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL: readers (web page, mcp) never block on the refresher's writes, and vice versa
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def pending_migrations(conn: sqlite3.Connection) -> list[Path]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS migrations ("
        " name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row["name"] for row in conn.execute("SELECT name FROM migrations")}
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in applied]


def migrate(conn: sqlite3.Connection) -> list[str]:
    applied = []
    for path in pending_migrations(conn):
        if not re.fullmatch(r"\d{4}_[a-z0-9_]+\.sql", path.name):
            raise ValueError(
                f"bad migration file name: {path.name} (want e.g. 0002_add_salary.sql)"
            )
        now = datetime.now(UTC).isoformat()
        script = (
            "BEGIN;\n"
            f"{path.read_text()}\n;\n"
            f"INSERT INTO migrations (name, applied_at) VALUES ('{path.name}', '{now}');\n"
            "COMMIT;"
        )
        try:
            conn.executescript(script)
        except sqlite3.Error:
            conn.rollback()
            raise
        applied.append(path.name)
    return applied


def add_company(conn: sqlite3.Connection, company: Company) -> int:
    with conn:
        cur = conn.execute(
            """
            INSERT INTO companies (
                name, ats, board, website, career_site, description, tags,
                employees_min, employees_max, company_type, yc_slug, added_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company.name,
                company.ats,
                company.board,
                company.website,
                company.career_site,
                company.description,
                json.dumps(company.tags),
                company.employees_min,
                company.employees_max,
                company.company_type,
                company.yc_slug,
                datetime.now(UTC).isoformat(),
            ),
        )
    company_id = cur.lastrowid
    assert company_id is not None
    return company_id


def update_company(conn: sqlite3.Connection, company: Company) -> None:
    assert company.id is not None
    with conn:
        conn.execute(
            """
            UPDATE companies SET
                name = ?, ats = ?, board = ?, website = ?, career_site = ?,
                description = ?, tags = ?, employees_min = ?, employees_max = ?,
                company_type = ?, yc_slug = ?
            WHERE id = ?
            """,
            (
                company.name,
                company.ats,
                company.board,
                company.website,
                company.career_site,
                company.description,
                json.dumps(company.tags),
                company.employees_min,
                company.employees_max,
                company.company_type,
                company.yc_slug,
                company.id,
            ),
        )


def list_companies(conn: sqlite3.Connection) -> list[Company]:
    rows = conn.execute("SELECT * FROM companies ORDER BY name")
    return [_to_company(row) for row in rows]


def list_scrape_targets(conn: sqlite3.Connection) -> list[ScrapeTarget]:
    # a real ats wins; companies without one fall back to their YC jobs page
    rows = conn.execute(
        """
        SELECT id, name, COALESCE(ats, 'yc') AS ats, COALESCE(board, yc_slug) AS board
        FROM companies
        WHERE (ats IS NOT NULL AND board IS NOT NULL) OR yc_slug IS NOT NULL
        ORDER BY name
        """
    )
    return [
        ScrapeTarget(row["id"], row["name"], row["ats"], row["board"]) for row in rows
    ]


def _to_company(row: sqlite3.Row) -> Company:
    return Company(
        id=row["id"],
        name=row["name"],
        ats=row["ats"],
        board=row["board"],
        website=row["website"],
        career_site=row["career_site"],
        description=row["description"],
        tags=json.loads(row["tags"]),
        employees_min=row["employees_min"],
        employees_max=row["employees_max"],
        company_type=row["company_type"],
        yc_slug=row["yc_slug"],
    )


def save_jobs(
    conn: sqlite3.Connection, company_id: int, jobs: list[Job]
) -> tuple[int, int]:
    # returns (new jobs, jobs closed because this scrape no longer lists them)
    now = datetime.now(UTC).isoformat()
    new = 0
    with conn:
        for job in jobs:
            row = conn.execute(UPSERT, _to_row(job, company_id, now)).fetchone()
            new += row["is_new"]
        # every job this scrape returned now has last_seen = now; anything older is gone
        closed = conn.execute(
            "UPDATE jobs SET closed_at = ?"
            " WHERE company_id = ? AND last_seen < ? AND closed_at IS NULL",
            (now, company_id, now),
        ).rowcount
    return new, closed


def known_external_ids(conn: sqlite3.Connection, source: str) -> frozenset[str]:
    rows = conn.execute(
        "SELECT external_id FROM jobs WHERE source = ? AND description <> ''", (source,)
    )
    return frozenset(row["external_id"] for row in rows)


def count_jobs(conn: sqlite3.Connection) -> tuple[int, int]:
    row = conn.execute(
        "SELECT COUNT(*) - COUNT(closed_at) AS open, COUNT(closed_at) AS closed FROM jobs"
    ).fetchone()
    return row["open"], row["closed"]


def enrichment_state(conn: sqlite3.Connection, method: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT j.id, j.role, j.location, j.description, e.version, e.input_hash
        FROM jobs j
        LEFT JOIN job_enrichment e ON e.job_id = j.id AND e.method = ?
        """,
        (method,),
    ).fetchall()


def save_enrichments(
    conn: sqlite3.Connection,
    method: str,
    version: int,
    results: list[tuple[int, str, Enrichment]],
) -> None:
    now = datetime.now(UTC).isoformat()
    with conn:
        conn.executemany(
            """
            INSERT INTO job_enrichment (
                job_id, method, version, input_hash, enriched_at, work_type, min_loe,
                max_loe, salary, visa, skills, seniority, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (job_id, method) DO UPDATE SET
                version = excluded.version, input_hash = excluded.input_hash,
                enriched_at = excluded.enriched_at, work_type = excluded.work_type,
                min_loe = excluded.min_loe, max_loe = excluded.max_loe,
                salary = excluded.salary, visa = excluded.visa, skills = excluded.skills,
                seniority = excluded.seniority, category = excluded.category
            """,
            [
                (
                    job_id, method, version, input_hash, now, e.work_type, e.min_loe,
                    e.max_loe, e.salary, e.visa, json.dumps(e.skills), e.seniority, e.category,
                )
                for job_id, input_hash, e in results
            ],
        )


def search_jobs(conn: sqlite3.Connection, query: SearchQuery) -> list[sqlite3.Row]:
    where: list[str] = []
    params: list[object] = []

    if query.terms:
        where.append("jobs_fts MATCH ?")
        params.append(" ".join(query.terms) if query.raw else _fts_quote(query.terms))
    if query.work_type:
        where.append("j.work_type = ?")
        params.append(query.work_type)
    if query.company_type:
        where.append("c.company_type = ?")
        params.append(query.company_type)
    if query.tag:
        where.append("EXISTS (SELECT 1 FROM json_each(c.tags) WHERE value = ?)")
        params.append(query.tag)
    if query.company:
        where.append("c.name LIKE ?")
        params.append(f"%{query.company}%")
    if query.location:
        where.append("j.location LIKE ?")
        params.append(f"%{query.location}%")
    if query.max_employees is not None:
        where.append("c.employees_max <= ?")
        params.append(query.max_employees)
    if query.seniority:
        where.append("j.seniority = ?")
        params.append(query.seniority)
    if query.category:
        where.append("j.category = ?")
        params.append(query.category)
    if query.skill:
        where.append("EXISTS (SELECT 1 FROM json_each(j.skills) WHERE value = ?)")
        params.append(query.skill.lower())
    if query.years is not None:
        # jobs you qualify for: no stated requirement, or one you meet
        where.append("(j.min_loe IS NULL OR j.min_loe <= ?)")
        params.append(query.years)
    if not query.include_closed:
        where.append("j.closed_at IS NULL")
    if query.hide_tracked_for is not None:
        where.append(
            "NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id = j.id AND a.profile_id = ?)"
        )
        params.append(query.hide_tracked_for)
    if query.days is not None:
        since = datetime.now(UTC) - timedelta(days=query.days)
        where.append("COALESCE(j.published, j.first_seen) >= ?")
        params.append(since.isoformat())

    sql = """
        SELECT j.id, j.role, j.location, j.work_type, j.published, j.first_seen,
               j.salary, j.seniority, j.category, c.name AS company
        FROM job_view j
        JOIN companies c ON c.id = j.company_id
    """
    if query.terms:
        sql += " JOIN jobs_fts ON jobs_fts.rowid = j.id"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if query.terms:
        sql += " ORDER BY bm25(jobs_fts, 10.0, 5.0, 2.0, 1.0)"
    else:
        sql += " ORDER BY COALESCE(j.published, j.first_seen) DESC"
    sql += " LIMIT ?"
    params.append(query.limit)

    return conn.execute(sql, params).fetchall()


def get_job(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT j.*, c.name AS company_name, c.website, c.description AS company_description,
               c.tags, c.employees_min, c.employees_max, c.company_type
        FROM job_view j
        JOIN companies c ON c.id = j.company_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()


def _fts_quote(terms: list[str]) -> str:
    return " ".join('"' + term.replace('"', "") + '"' for term in terms)


def _to_row(job: Job, company_id: int, now: str) -> dict:
    return {
        "company_id": company_id,
        "source": job.source,
        "external_id": job.external_id,
        "company": job.company,
        "role": job.role,
        "location": job.location,
        "official_posting_url": job.official_posting_url,
        "description": job.description,
        "published": to_iso(job.published),
        "deadline": to_iso(job.deadline),
        "work_type": job.work_type,
        "min_loe": job.min_loe,
        "skills": json.dumps(job.skills),
        "salary": job.salary,
        "equity": job.equity,
        "visa": job.visa,
        "recruiter_detail": json.dumps(job.recruiter_detail),
        "raw": json.dumps(job.raw),
        "now": now,
    }


def get_state(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = conn.execute("SELECT key, value FROM app_state").fetchall()
    except sqlite3.OperationalError:  # before migration 0007
        return {}
    return {row["key"]: row["value"] for row in rows}


def set_state(conn: sqlite3.Connection, **values: str | None) -> None:
    with conn:
        for key, value in values.items():
            if value is None:
                conn.execute("DELETE FROM app_state WHERE key = ?", (key,))
            else:
                conn.execute(
                    "INSERT INTO app_state (key, value) VALUES (?, ?)"
                    " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )


def companies_to_discover(conn: sqlite3.Connection, checked_before: str) -> list[Company]:
    rows = conn.execute(
        "SELECT * FROM companies WHERE ats IS NULL"
        " AND (ats_checked_at IS NULL OR ats_checked_at < ?) ORDER BY name",
        (checked_before,),
    )
    return [_to_company(row) for row in rows]


def mark_ats_checked(conn: sqlite3.Connection, company_ids: list[int], when: str) -> None:
    with conn:
        conn.executemany(
            "UPDATE companies SET ats_checked_at = ? WHERE id = ?",
            [(when, company_id) for company_id in company_ids],
        )


def count_companies(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"]


def create_profile(conn: sqlite3.Connection, name: str, about: str = "") -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO profiles (name, about, created_at) VALUES (?, ?, ?)",
            (name, about, datetime.now(UTC).isoformat()),
        )
    profile_id = cur.lastrowid
    assert profile_id is not None
    return profile_id


def list_profiles(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.id, p.name, p.about, p.created_at, COUNT(a.id) AS tracked
        FROM profiles p LEFT JOIN applications a ON a.profile_id = p.id
        GROUP BY p.id ORDER BY p.name
        """
    ).fetchall()


def get_profile(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM profiles WHERE name = ?", (name,)).fetchone()


def delete_profile(conn: sqlite3.Connection, profile_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))


def track_application(
    conn: sqlite3.Connection, profile_id: int, job_id: int, status: str, note: str, at: str
) -> None:
    now = datetime.now(UTC).isoformat()
    with conn:
        existing = conn.execute(
            "SELECT id, applied_at FROM applications WHERE profile_id = ? AND job_id = ?",
            (profile_id, job_id),
        ).fetchone()
        # applied_at is set the first time the status becomes "applied", then kept
        applied_at = existing["applied_at"] if existing else None
        if applied_at is None and status == "applied":
            applied_at = at
        if existing is None:
            application_id = conn.execute(
                "INSERT INTO applications"
                " (profile_id, job_id, status, applied_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (profile_id, job_id, status, applied_at, now, now),
            ).lastrowid
        else:
            application_id = existing["id"]
            conn.execute(
                "UPDATE applications SET status = ?, applied_at = ?, updated_at = ? WHERE id = ?",
                (status, applied_at, now, application_id),
            )
        conn.execute(
            "INSERT INTO application_events (application_id, status, note, at) VALUES (?, ?, ?, ?)",
            (application_id, status, note, at),
        )


def list_applications(
    conn: sqlite3.Connection, profile_id: int, status: str | None = None
) -> list[sqlite3.Row]:
    sql = """
        SELECT a.job_id, a.status, a.applied_at, a.updated_at, j.role, c.name AS company,
               j.location, j.closed_at, j.official_posting_url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        JOIN companies c ON c.id = j.company_id
        WHERE a.profile_id = ?
    """
    params: list[object] = [profile_id]
    if status:
        sql += " AND a.status = ?"
        params.append(status)
    sql += " ORDER BY a.updated_at DESC"
    return conn.execute(sql, params).fetchall()


def get_application(
    conn: sqlite3.Connection, profile_id: int, job_id: int
) -> tuple[sqlite3.Row, list[sqlite3.Row]] | None:
    application = conn.execute(
        """
        SELECT a.id, a.job_id, a.status, a.applied_at, a.created_at, a.updated_at,
               j.role, c.name AS company, j.location, j.closed_at, j.official_posting_url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        JOIN companies c ON c.id = j.company_id
        WHERE a.profile_id = ? AND a.job_id = ?
        """,
        (profile_id, job_id),
    ).fetchone()
    if application is None:
        return None
    events = conn.execute(
        "SELECT status, note, at FROM application_events WHERE application_id = ? ORDER BY at, id",
        (application["id"],),
    ).fetchall()
    return application, events


def delete_application(conn: sqlite3.Connection, profile_id: int, job_id: int) -> bool:
    with conn:
        cur = conn.execute(
            "DELETE FROM applications WHERE profile_id = ? AND job_id = ?", (profile_id, job_id)
        )
    return cur.rowcount > 0


def profile_activity(conn: sqlite3.Connection, profile_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT a.id AS application_id, a.job_id, a.status AS current_status, a.applied_at,
               e.status AS event_status, e.at, j.role, c.name AS company, j.category, j.seniority
        FROM application_events e
        JOIN applications a ON a.id = e.application_id
        JOIN job_view j ON j.id = a.job_id
        JOIN companies c ON c.id = j.company_id
        WHERE a.profile_id = ?
        ORDER BY e.at, e.id
        """,
        (profile_id,),
    )
    return [dict(row) for row in rows]
