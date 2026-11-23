import json
import sqlite3
from datetime import UTC, datetime

from magstrel.models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                   INTEGER PRIMARY KEY,
    source               TEXT NOT NULL,
    external_id          TEXT NOT NULL,
    company              TEXT NOT NULL,
    role                 TEXT NOT NULL,
    location             TEXT NOT NULL,
    official_posting_url TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    published            TEXT,
    deadline             TEXT,

    work_type            TEXT,
    min_loe              INTEGER,
    max_loe              INTEGER,
    company_type         TEXT,
    skills               TEXT NOT NULL DEFAULT '[]',
    meta                 TEXT NOT NULL DEFAULT '[]',
    recruiter_detail     TEXT NOT NULL DEFAULT '{}',

    raw                  TEXT NOT NULL,

    first_seen           TEXT NOT NULL,
    last_seen            TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'new',

    UNIQUE (source, external_id)
);
"""

UPSERT = """
INSERT INTO jobs (
    source, external_id, company, role, location, official_posting_url,
    description, published, deadline, raw, first_seen, last_seen
) VALUES (
    :source, :external_id, :company, :role, :location, :official_posting_url,
    :description, :published, :deadline, :raw, :now, :now
)
ON CONFLICT (source, external_id) DO UPDATE SET
    company              = excluded.company,
    role                 = excluded.role,
    location             = excluded.location,
    official_posting_url = excluded.official_posting_url,
    description          = excluded.description,
    published            = excluded.published,
    deadline             = excluded.deadline,
    raw                  = excluded.raw,
    last_seen            = excluded.last_seen
RETURNING first_seen = last_seen AS is_new
"""


def connect(path: str = "jobs.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_jobs(conn: sqlite3.Connection, jobs: list[Job]) -> int:
    now = datetime.now(UTC).isoformat()
    new = 0
    with conn:
        for job in jobs:
            row = conn.execute(UPSERT, _to_row(job, now)).fetchone()
            new += row["is_new"]
    return new


def count_jobs(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()["total"]


def _to_row(job: Job, now: str) -> dict:
    return {
        "source": job.source,
        "external_id": job.external_id,
        "company": job.company,
        "role": job.role,
        "location": job.location,
        "official_posting_url": job.official_posting_url,
        "description": job.description,
        "published": _iso(job.published),
        "deadline": _iso(job.deadline),
        "raw": json.dumps(job.raw),
        "now": now,
    }


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
