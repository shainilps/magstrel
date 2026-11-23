import logging
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from functools import partial

from magstrel import db
from magstrel.enrich import rules
from magstrel.models import Company, Job, ScrapeTarget
from magstrel.sources.company import discover
from magstrel.sources.company import yc as yc_companies
from magstrel.sources.job import SOURCES, hn, smartrecruiters
from magstrel.sources.job import yc as yc_jobs

log = logging.getLogger("magstrel")

Fetch = Callable[[str, str], list[Job]]
# called as progress(done, total) while a step works through its list
Progress = Callable[[int, int], None]


COMPANIES_EVERY = timedelta(days=1)
RECHECK_BOARDS_AFTER = timedelta(days=30)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def refresh_all(conn: sqlite3.Connection, step: Callable[[str], None]) -> None:
    last_import = db.get_state(conn).get("companies_imported_at")
    if last_import is None or datetime.fromisoformat(last_import) < datetime.now(UTC) - COMPANIES_EVERY:
        step("importing the YC company list")
        import_yc(conn)
        discover_boards(conn, progress=lambda done, total: step(f"finding job boards {done}/{total} companies"))
    scrape_jobs(conn, progress=lambda done, total: step(f"scraping jobs {done}/{total} companies"))
    step("reading HN 'Who is hiring?'")
    scrape_hn(conn)
    step("enriching new jobs")
    enrich_jobs(conn)


def scrape_jobs(
    conn: sqlite3.Connection,
    only: str | None = None,
    workers: int = 8,
    progress: Progress | None = None,
) -> int:
    if only == "hn":
        return scrape_hn(conn)
    targets = db.list_scrape_targets(conn)
    if only:
        targets = [t for t in targets if t.ats == only]
    targets.sort(key=lambda t: t.ats == "yc")  # yc is throttled to 1 request/s: fast sources first

    # these two fetch a description per job, so they skip the ones we already have
    sources = SOURCES | {
        "yc": partial(yc_jobs.fetch, known_ids=db.known_external_ids(conn, "yc")),
        "smartrecruiters": partial(
            smartrecruiters.fetch, known_ids=db.known_external_ids(conn, "smartrecruiters")
        ),
    }
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch, target, sources): target for target in targets}
        for done, future in enumerate(as_completed(futures), start=1):
            target = futures[future]
            if progress:
                progress(done, len(targets))
            try:
                jobs = future.result()
            except Exception as err:  # noqa: BLE001
                log.warning("%s: FAILED (%s)", target.name, err)
                continue
            new, closed = db.save_jobs(conn, target.company_id, jobs)
            log.info("%s: %d fetched, %d new, %d closed", target.name, len(jobs), new, closed)

    open_jobs, closed_jobs = db.count_jobs(conn)
    log.info("database: %d open jobs, %d closed", open_jobs, closed_jobs)
    if only is None:
        db.set_state(conn, jobs_scraped_at=now_iso())
    return len(targets)


def _fetch(target: ScrapeTarget, sources: dict[str, Fetch]) -> list[Job]:
    fetch = sources.get(target.ats)
    if fetch is None:
        raise ValueError(f"unknown ats {target.ats!r}")
    return fetch(target.board, target.name)


def enrich_jobs(conn: sqlite3.Connection, force: bool = False) -> int:
    todo = []
    for row in db.enrichment_state(conn, rules.METHOD):
        input_hash = rules.input_hash(row["role"], row["location"], row["description"])
        outdated = row["version"] is None or row["version"] < rules.VERSION
        if force or outdated or row["input_hash"] != input_hash:
            todo.append((row, input_hash))

    if todo:
        log.info("enriching %d jobs with rules v%d...", len(todo), rules.VERSION)
        results = [
            (row["id"], input_hash, rules.enrich(row["role"], row["location"], row["description"]))
            for row, input_hash in todo
        ]
        db.save_enrichments(conn, rules.METHOD, rules.VERSION, results)
        for field_name in ("work_type", "seniority", "category", "min_loe", "salary", "visa", "skills"):
            filled = sum(1 for _, _, e in results if getattr(e, field_name))
            log.info("  %-10s found for %6d of %d", field_name, filled, len(results))
    else:
        log.info("everything is already enriched")
    db.set_state(conn, enriched_at=now_iso())
    return len(todo)


def import_yc(conn: sqlite3.Connection, include_all: bool = False) -> tuple[int, int]:
    log.info("downloading YC company list...")
    existing = {c.name.lower(): c for c in db.list_companies(conn)}
    added = updated = 0
    for company in yc_companies.fetch_companies(include_all=include_all):
        current = existing.get(company.name.lower())
        if current is None:
            company.id = db.add_company(conn, company)
            existing[company.name.lower()] = company
            added += 1
        else:
            _fill_missing(current, company)
            db.update_company(conn, current)
            updated += 1
    log.info("added %d companies, updated %d existing ones", added, updated)
    db.set_state(conn, companies_imported_at=now_iso())
    return added, updated



def scrape_hn(conn: sqlite3.Connection) -> int:
    started = now_iso()
    by_company: dict[str, list[Job]] = {}
    for company, job in hn.fetch_latest():
        by_company.setdefault(company, []).append(job)

    new = 0
    for name, jobs in by_company.items():
        company_id = db.company_id_by_name(conn, name) or db.add_company(
            conn, Company(name=name, tags=["hn-hiring"])
        )
        new += db.save_jobs(conn, company_id, jobs, close_missing=False)[0]
    # posts not in the current thread (last month's, or deleted) are closed
    closed = db.close_unseen(conn, "hn", started)
    posts = sum(len(jobs) for jobs in by_company.values())
    log.info("HN who is hiring: %d posts from %d companies, %d new, %d closed", posts, len(by_company), new, closed)
    db.set_state(conn, hn_scraped_at=now_iso())
    return posts


def verify_boards(
    conn: sqlite3.Connection, workers: int = 8, company: str | None = None
) -> list[dict]:
    targets = [t for t in db.list_scrape_targets(conn) if t.ats in SOURCES]
    if company:
        targets = [t for t in targets if t.name.lower() == company.lower()]
    companies = {c.id: c for c in db.linked_companies(conn)}
    websites = {company_id: c.website for company_id, c in companies.items()}
    log.info("checking the job boards of %d companies...", len(targets))
    suspects: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(discover.verify_board, t.ats, t.board, t.name, websites.get(t.company_id)): t
            for t in targets
        }
        for future in as_completed(futures):
            target = futures[future]
            try:
                verdict = future.result()
            except Exception as err:  # noqa: BLE001
                log.warning("%s: couldn't check (%s)", target.name, err)
                continue
            # report only: genuine companies sometimes never write their own name in a posting,
            # so a human decides (magstrel company unlink NAME). None = no jobs, nothing to judge
            if verdict is False:
                samples = db.sample_jobs(conn, target.company_id, target.ats)
                details = companies[target.company_id]
                suspects.append(
                    {
                        "company": target.name,
                        "board": f"{target.ats}/{target.board}",
                        "company_website": details.website,
                        "company_description": details.description,
                        "sample_jobs_on_board": [dict(row) for row in samples],
                    }
                )
                example = samples[0]["role"] if samples else ""
                log.info("suspect: %s -> %s/%s  (e.g. %r)", target.name, target.ats, target.board, example)
    log.info("%d suspects out of %d", len(suspects), len(targets))
    return suspects



def unlink_company(conn: sqlite3.Connection, name: str) -> int | None:
    # returns how many jobs were closed, or None when there's no such company
    company_id = db.company_id_by_name(conn, name)
    if company_id is None:
        return None
    closed = db.unlink_board(conn, company_id)
    log.info("unlinked %s's job board, closed %d jobs", name, closed)
    return closed


def _fill_missing(current: Company, new: Company) -> None:
    # never overwrite what you already set; only fill gaps and add tags
    current.website = current.website or new.website
    current.description = current.description or new.description
    current.employees_min = current.employees_min or new.employees_min
    current.employees_max = current.employees_max or new.employees_max
    current.company_type = current.company_type or new.company_type
    current.yc_slug = current.yc_slug or new.yc_slug
    current.tags += [t for t in new.tags if t not in current.tags]


def discover_boards(
    conn: sqlite3.Connection,
    limit: int | None = None,
    workers: int = 8,
    recheck_all: bool = False,
    progress: Progress | None = None,
) -> int:
    # companies checked recently without luck are skipped: retrying them every run is pointless
    checked_before = now_iso() if recheck_all else (datetime.now(UTC) - RECHECK_BOARDS_AFTER).isoformat()
    todo = db.companies_to_discover(conn, checked_before)[:limit]
    log.info("looking up job boards for %d companies...", len(todo))

    found = 0
    checked: list[int] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(discover.find_board, c.name, c.website): c for c in todo}
        for done, future in enumerate(as_completed(futures), start=1):
            company = futures[future]
            if progress:
                progress(done, len(todo))
            try:
                result = future.result()
            except Exception as err:  # noqa: BLE001
                log.warning("%s: ERROR (%s)", company.name, err)  # not marked: retried next run
                continue
            assert company.id is not None
            checked.append(company.id)
            if result is None:
                continue
            company.ats, company.board = result
            try:
                db.update_company(conn, company)
            except sqlite3.IntegrityError:
                log.warning("%s: %s/%s already belongs to another company", company.name, *result)
                continue
            found += 1
            log.info("%s: %s/%s", company.name, company.ats, company.board)

    db.mark_ats_checked(conn, checked, now_iso())
    db.set_state(conn, boards_checked_at=now_iso())
    log.info("found %d of %d", found, len(todo))
    return found
