from collections import Counter
from datetime import datetime, timedelta
from typing import Any

HEARD_BACK = {"interviewing", "offer", "rejected"}
NO_NEWS_AFTER = timedelta(days=14)


def profile_stats(activity: list[dict[str, Any]], now: datetime, days: int) -> dict[str, Any]:
    # activity: one row per status change, each carrying its application's job details
    since = now - timedelta(days=days)
    applications: dict[int, list[dict[str, Any]]] = {}
    for row in sorted(activity, key=lambda r: r["at"]):
        applications.setdefault(row["application_id"], []).append(row)

    applied_rows = [r for r in activity if r["event_status"] == "applied"]
    recent = [r for r in activity if _at(r) >= since]
    last_applied = max(applied_rows, key=lambda r: r["at"], default=None)

    return {
        "period": {"days": days, "since": since.date().isoformat()},
        "tracked_total": len(applications),
        "current_status": dict(Counter(events[-1]["current_status"] for events in applications.values())),
        "in_period": dict(Counter(r["event_status"] for r in recent)),
        "applied_per_week": _per_week([r for r in recent if r["event_status"] == "applied"]),
        "last_applied": _job(last_applied) | {"at": last_applied["at"]} if last_applied else None,
        "funnel_all_time": _funnel(applications),
        "avg_days_to_first_response": _avg_response_days(applications),
        "no_news_for_14_days": _waiting(applications, now),
        "applied_by_category": dict(Counter(r["category"] or "unknown" for r in applied_rows)),
        "applied_by_seniority": dict(Counter(r["seniority"] or "unknown" for r in applied_rows)),
    }


def _funnel(applications: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    applied = heard = interviews = offers = 0
    for events in applications.values():
        statuses = [e["event_status"] for e in events]
        if "applied" not in statuses:
            continue  # only saved / not_interested: not part of the funnel
        after = statuses[statuses.index("applied") + 1 :]
        applied += 1
        heard += any(s in HEARD_BACK for s in after)
        interviews += any(s in ("interviewing", "offer") for s in after)
        offers += "offer" in after
    rate = lambda n: round(n / applied, 2) if applied else None  # noqa: E731
    return {
        "applied": applied,
        "heard_back": heard,
        "interviewing": interviews,
        "offer": offers,
        "response_rate": rate(heard),
        "interview_rate": rate(interviews),
        "offer_rate": rate(offers),
    }


def _avg_response_days(applications: dict[int, list[dict[str, Any]]]) -> float | None:
    waits = []
    for events in applications.values():
        applied = next((e for e in events if e["event_status"] == "applied"), None)
        if applied is None:
            continue
        reply = next((e for e in events if e["event_status"] in HEARD_BACK and e["at"] > applied["at"]), None)
        if reply:
            waits.append((_at(reply) - _at(applied)).total_seconds() / 86400)
    return round(sum(waits) / len(waits), 1) if waits else None


def _waiting(applications: dict[int, list[dict[str, Any]]], now: datetime) -> list[dict[str, Any]]:
    waiting = []
    for events in applications.values():
        latest = events[-1]
        if latest["current_status"] == "applied" and latest["applied_at"]:
            waited = now - datetime.fromisoformat(latest["applied_at"])
            if waited >= NO_NEWS_AFTER:
                waiting.append(_job(latest) | {"days_waiting": waited.days})
    return sorted(waiting, key=lambda w: -w["days_waiting"])


def _per_week(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weeks = Counter((_at(r) - timedelta(days=_at(r).weekday())).date().isoformat() for r in rows)
    return [{"week_of": week, "applied": count} for week, count in sorted(weeks.items())]


def _job(row: dict[str, Any]) -> dict[str, Any]:
    return {"job_id": row["job_id"], "company": row["company"], "role": row["role"]}


def _at(row: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(row["at"])
