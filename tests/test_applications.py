import sqlite3

import pytest

from magstrel import db
from magstrel.models import Company, Job, SearchQuery


@pytest.fixture
def conn(tmp_path):
    # a brand-new database per test: migrated, with one company and two jobs
    conn = db.connect(tmp_path / "test.db")
    db.migrate(conn)
    company_id = db.add_company(conn, Company(name="Acme"))
    db.save_jobs(conn, company_id, [_job("1", "Backend Engineer"), _job("2", "Frontend Engineer")])
    yield conn
    conn.close()


def _job(external_id: str, role: str) -> Job:
    return Job(
        raw={},
        source="test",
        external_id=external_id,
        company="Acme",
        role=role,
        location="Remote",
        official_posting_url=f"https://example.com/{external_id}",
    )


def _job_id(conn, role: str) -> int:
    return conn.execute("SELECT id FROM jobs WHERE role = ?", (role,)).fetchone()["id"]


def test_profile_names_are_unique_ignoring_case(conn):
    db.create_profile(conn, "Shainil")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_profile(conn, "shainil")
    assert db.get_profile(conn, "SHAINIL")["name"] == "Shainil"


def test_tracking_keeps_history_and_first_applied_date(conn):
    profile_id = db.create_profile(conn, "me")
    job_id = _job_id(conn, "Backend Engineer")

    db.track_application(conn, profile_id, job_id, "saved", "", "2026-11-01T00:00:00+00:00")
    db.track_application(conn, profile_id, job_id, "applied", "via referral", "2026-11-03T00:00:00+00:00")
    db.track_application(conn, profile_id, job_id, "interviewing", "", "2026-11-12T00:00:00+00:00")

    application, events = db.get_application(conn, profile_id, job_id)
    assert application["status"] == "interviewing"
    assert application["applied_at"] == "2026-11-03T00:00:00+00:00"
    assert [e["status"] for e in events] == ["saved", "applied", "interviewing"]
    assert events[1]["note"] == "via referral"


def test_list_applications_filters_by_status(conn):
    profile_id = db.create_profile(conn, "me")
    now = "2026-11-23T00:00:00+00:00"
    db.track_application(conn, profile_id, _job_id(conn, "Backend Engineer"), "applied", "", now)
    db.track_application(conn, profile_id, _job_id(conn, "Frontend Engineer"), "rejected", "", now)

    assert len(db.list_applications(conn, profile_id)) == 2
    assert [r["role"] for r in db.list_applications(conn, profile_id, "applied")] == ["Backend Engineer"]


def test_profiles_dont_see_each_others_applications(conn):
    me, friend = db.create_profile(conn, "me"), db.create_profile(conn, "friend")
    db.track_application(conn, me, _job_id(conn, "Backend Engineer"), "applied", "", "2026-11-23T00:00:00+00:00")
    assert db.list_applications(conn, friend) == []


def test_search_can_hide_jobs_a_profile_already_tracked(conn):
    profile_id = db.create_profile(conn, "me")
    db.track_application(conn, profile_id, _job_id(conn, "Backend Engineer"), "applied", "", "2026-11-23T00:00:00+00:00")

    roles = lambda query: sorted(r["role"] for r in db.search_jobs(conn, query))  # noqa: E731
    assert roles(SearchQuery()) == ["Backend Engineer", "Frontend Engineer"]
    assert roles(SearchQuery(hide_tracked_for=profile_id)) == ["Frontend Engineer"]


def test_tracking_an_unknown_job_fails(conn):
    profile_id = db.create_profile(conn, "me")
    with pytest.raises(sqlite3.IntegrityError):
        db.track_application(conn, profile_id, 999999, "applied", "", "2026-11-23T00:00:00+00:00")


def test_deleting_a_profile_deletes_its_applications_and_history(conn):
    profile_id = db.create_profile(conn, "me")
    db.track_application(conn, profile_id, _job_id(conn, "Backend Engineer"), "applied", "", "2026-11-23T00:00:00+00:00")
    db.delete_profile(conn, profile_id)
    assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM application_events").fetchone()[0] == 0
