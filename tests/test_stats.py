from datetime import UTC, datetime

from magstrel.stats import profile_stats

NOW = datetime(2026, 11, 23, tzinfo=UTC)


def _event(app_id, status, at, current, applied_at=None, category="backend"):
    return {
        "application_id": app_id,
        "job_id": 100 + app_id,
        "company": f"Company {app_id}",
        "role": f"Role {app_id}",
        "category": category,
        "seniority": "senior",
        "current_status": current,
        "applied_at": applied_at,
        "event_status": status,
        "at": f"{at}T00:00:00+00:00",
    }


ACTIVITY = [
    # 1: applied, interview after 5 days, then offer
    _event(1, "applied", "2026-11-02", "offer", "2026-11-02T00:00:00+00:00"),
    _event(1, "interviewing", "2026-11-07", "offer", "2026-11-02T00:00:00+00:00"),
    _event(1, "offer", "2026-11-15", "offer", "2026-11-02T00:00:00+00:00"),
    # 2: applied, rejected after 3 days
    _event(2, "applied", "2026-11-04", "rejected", "2026-11-04T00:00:00+00:00"),
    _event(2, "rejected", "2026-11-07", "rejected", "2026-11-04T00:00:00+00:00"),
    # 3: applied 20 days ago, no news
    _event(3, "applied", "2026-11-03", "applied", "2026-11-03T00:00:00+00:00", category="data"),
    # 4: only saved, not part of the funnel
    _event(4, "saved", "2026-11-20", "saved"),
    # 5: applied long before the period
    _event(5, "applied", "2026-08-01", "applied", "2026-08-01T00:00:00+00:00"),
]


def test_funnel_counts_only_applied_jobs():
    funnel = profile_stats(ACTIVITY, NOW, days=30)["funnel_all_time"]
    assert funnel == {
        "applied": 4,
        "heard_back": 2,
        "interviewing": 1,
        "offer": 1,
        "response_rate": 0.5,
        "interview_rate": 0.25,
        "offer_rate": 0.25,
    }


def test_period_only_counts_recent_events():
    stats = profile_stats(ACTIVITY, NOW, days=30)
    assert stats["in_period"]["applied"] == 3  # job 5 applied in August is outside
    assert stats["tracked_total"] == 5
    assert stats["current_status"] == {"offer": 1, "rejected": 1, "applied": 2, "saved": 1}


def test_last_applied_and_average_response_time():
    stats = profile_stats(ACTIVITY, NOW, days=30)
    assert stats["last_applied"]["job_id"] == 102  # 2026-11-04 is the latest "applied"
    assert stats["avg_days_to_first_response"] == 4.0  # (5 + 3) / 2


def test_applications_without_news_for_two_weeks():
    waiting = profile_stats(ACTIVITY, NOW, days=30)["no_news_for_14_days"]
    assert [w["job_id"] for w in waiting] == [105, 103]  # longest wait first


def test_applied_per_week_starts_on_monday():
    weeks = profile_stats(ACTIVITY, NOW, days=30)["applied_per_week"]
    assert weeks == [{"week_of": "2026-11-02", "applied": 3}]


def test_empty_profile():
    stats = profile_stats([], NOW, days=30)
    assert stats["tracked_total"] == 0
    assert stats["last_applied"] is None
    assert stats["funnel_all_time"]["response_rate"] is None
