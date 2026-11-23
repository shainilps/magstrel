import pytest

from magstrel.sources.job.hn import parse_post


def _comment(text: str) -> dict:
    return {"id": 123, "text": text, "created_at": "2026-11-02T16:40:00Z"}


@pytest.mark.parametrize(
    ("text", "company", "role", "location", "work_type", "salary"),
    [
        (
            'Simple Analytics | DevOps Engineer | REMOTE (worldwide, any timezone) | Full-time, 32h | €5,000/month | <a href="https://www.simpleanalytics.com/jobs/dev">https://www.simpleanalytics.com/jobs/dev</a><p>We are a privacy-first...',
            "Simple Analytics", "DevOps Engineer", "REMOTE (worldwide, any timezone)", "remote", "€5,000/month",
        ),
        (
            "Synteq | Growth Lead &amp; Systems Administrator | Austin, TX | REMOTE (US) | Full-time<p>About us",
            "Synteq", "Growth Lead & Systems Administrator", "Austin, TX | REMOTE (US)", "remote", None,
        ),
        (
            "MixRank (YC S11) | Software Engineers | 100% Remote (Global) | Full-Time<p>MixRank processes...",
            "MixRank", "Software Engineers", "100% Remote (Global)", "remote", None,
        ),
        (
            "Shepherd (Series B) | ONSITE | San Francisco, CA<p>We build insurance...",
            "Shepherd", "Hiring (see post)", "ONSITE | San Francisco, CA", "in-office", None,
        ),
    ],
)
def test_parses_standard_headers(text, company, role, location, work_type, salary):
    parsed_company, job = parse_post(_comment(text))
    assert parsed_company == company
    assert (job.role, job.location, job.work_type, job.salary) == (role, location, work_type, salary)


def test_link_to_the_company_page_is_preferred():
    _, job = parse_post(_comment('Acme | Engineer | REMOTE<p>Apply: <a href="https://acme.dev/jobs">acme.dev/jobs</a>'))
    assert job.official_posting_url == "https://acme.dev/jobs"


def test_falls_back_to_the_hn_link():
    _, job = parse_post(_comment("Acme | Engineer | REMOTE<p>Email jobs at acme dot dev"))
    assert job.official_posting_url == "https://news.ycombinator.com/item?id=123"


@pytest.mark.parametrize(
    "text",
    [
        "UPDATE (Nov 13): We're no longer taking applications for these roles.<p>Acme | Engineer | REMOTE",
        "Acme | Engineer | REMOTE<p>Edit: position has been filled, thanks everyone!",
        "Is anyone hiring juniors this month? Asking for a friend.",
        "",
    ],
)
def test_skips_closed_posts_and_non_posts(text):
    assert parse_post(_comment(text)) is None
