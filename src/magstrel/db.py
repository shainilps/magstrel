import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from magstrel.models import Job

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

UPSERT = """
INSERT INTO jobs (
    source, external_id, company, role, location, official_posting_url,
    description, published, deadline, work_type, raw, first_seen, last_seen
) VALUES (
    :source, :external_id, :company, :role, :location, :official_posting_url,
    :description, :published, :deadline, :work_type, :raw, :now, :now
)
ON CONFLICT (source, external_id) DO UPDATE SET
    company              = excluded.company,
    role                 = excluded.role,
    location             = excluded.location,
    official_posting_url = excluded.official_posting_url,
    description          = excluded.description,
    published            = excluded.published,
    deadline             = excluded.deadline,
    work_type            = COALESCE(excluded.work_type, jobs.work_type),
    raw                  = excluded.raw,
    last_seen            = excluded.last_seen
RETURNING first_seen = last_seen AS is_new
"""


def connect(path: str = "jobs.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
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
        "work_type": job.work_type,
        "raw": json.dumps(job.raw),
        "now": now,
    }


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
