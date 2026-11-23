import argparse
import json
import shutil
import sqlite3
import sys
import webbrowser
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import get_args

from magstrel import db
from magstrel.enrich import rules
from magstrel.models import (
    Category,
    Company,
    CompanyType,
    Job,
    ScrapeTarget,
    SearchQuery,
    Seniority,
    WorkType,
)
from magstrel.sources.company import discover
from magstrel.sources.company import yc as yc_companies
from magstrel.sources.job import ashby, greenhouse, lever
from magstrel.sources.job import yc as yc_jobs
from magstrel.utils import age, cut, format_employees, parse_csv, parse_employees

SOURCES = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="magstrel", description="Your own job database."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser(
        "migrate", help="apply pending database migrations"
    ).set_defaults(run=cmd_migrate)
    scrape = commands.add_parser(
        "scrape", help="fetch jobs from every scrapable company"
    )
    scrape.add_argument("--workers", type=int, default=8, help="parallel downloads")
    scrape.add_argument(
        "--only",
        choices=[*SOURCES, "yc"],
        help="scrape just one source, e.g. --only yc",
    )
    scrape.set_defaults(run=cmd_scrape)

    company = commands.add_parser("company", help="manage companies")
    company_commands = company.add_subparsers(dest="company_command", required=True)

    add = company_commands.add_parser("add", help="add a company")
    add.add_argument("name")
    add.add_argument("--ats", choices=SOURCES, help="job board system it uses")
    add.add_argument("--board", help="its board name on that ats, e.g. stripe")
    add.add_argument("--website", help="its homepage")
    add.add_argument("--career-site", help="url of its careers page")
    add.add_argument("--description", default="")
    add.add_argument(
        "--tags", default="", help="comma separated, e.g. fintech,payments"
    )
    add.add_argument("--employees", help="e.g. 50-200, 5000+ or 120")
    add.add_argument("--type", choices=get_args(CompanyType), dest="company_type")
    add.set_defaults(run=cmd_company_add)

    company_commands.add_parser("list", help="list companies").set_defaults(
        run=cmd_company_list
    )

    import_yc = company_commands.add_parser(
        "import-yc", help="import Y Combinator companies (active + hiring by default)"
    )
    import_yc.add_argument("--all", action="store_true", help="every YC company")
    import_yc.set_defaults(run=cmd_company_import_yc)

    find = company_commands.add_parser(
        "discover", help="find the ats + board for companies that don't have one"
    )
    find.add_argument("--limit", type=int, help="only try this many companies")
    find.add_argument("--workers", type=int, default=8, help="parallel lookups")
    find.set_defaults(run=cmd_company_discover)

    enrich = commands.add_parser(
        "enrich", help="work out seniority, category, skills, ... from each job's text"
    )
    enrich.add_argument("--all", action="store_true", help="redo every job, not just new ones")
    enrich.set_defaults(run=cmd_enrich)

    search = commands.add_parser("search", help="search jobs")
    search.add_argument(
        "terms", nargs="*", help="words to search for, e.g. rust backend"
    )
    search.add_argument(
        "--raw", action="store_true", help="use FTS5 syntax: OR, NOT, role:rust ..."
    )
    search.add_argument(
        "--remote", action="store_const", const="remote", dest="work_type"
    )
    search.add_argument("--work-type", choices=get_args(WorkType))
    search.add_argument("--type", choices=get_args(CompanyType), dest="company_type")
    search.add_argument("--tag", help="company tag, e.g. fintech or yc-backed")
    search.add_argument("--company", help="company name contains")
    search.add_argument("--location", help="location contains, e.g. london")
    search.add_argument("--max-employees", type=int)
    search.add_argument("--days", type=int, help="posted in the last N days")
    search.add_argument("--seniority", choices=get_args(Seniority))
    search.add_argument("--category", choices=get_args(Category))
    search.add_argument("--skill", help="e.g. python, rust, kubernetes")
    search.add_argument(
        "--years", type=int, help="your years of experience: hide jobs asking for more"
    )
    search.add_argument(
        "--closed", action="store_true", help="also show jobs that are no longer posted"
    )
    search.add_argument("--limit", type=int, default=30)
    search.set_defaults(run=cmd_search)

    show = commands.add_parser("show", help="show one job in full")
    show.add_argument("id", type=int)
    show.set_defaults(run=cmd_show)

    open_ = commands.add_parser("open", help="open a job posting in your browser")
    open_.add_argument("id", type=int)
    open_.set_defaults(run=cmd_open)

    args = parser.parse_args()
    conn = db.connect()
    try:
        if args.command != "migrate" and db.pending_migrations(conn):
            sys.exit("database is out of date, run: magstrel migrate")
        args.run(conn, args)
    finally:
        conn.close()


def cmd_migrate(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    applied = db.migrate(conn)
    for name in applied:
        print(f"applied {name}")
    if not applied:
        print("already up to date")


def cmd_scrape(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    targets = db.list_scrape_targets(conn)
    if args.only:
        targets = [t for t in targets if t.ats == args.only]
    if not targets:
        sys.exit("nothing to scrape, add companies with: magstrel company add ...")
    targets.sort(key=lambda t: t.ats == "yc")

    sources = SOURCES | {
        "yc": partial(yc_jobs.fetch, known_ids=db.known_external_ids(conn, "yc"))
    }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_fetch, target, sources): target for target in targets}
        for future in as_completed(futures):
            target = futures[future]
            try:
                jobs = future.result()
            except Exception as err:  # noqa: BLE001
                print(f"{target.name}: FAILED ({err})")
                continue
            new, closed = db.save_jobs(conn, target.company_id, jobs)
            print(f"{target.name}: {len(jobs)} fetched, {new} new, {closed} closed")
    open_jobs, closed_jobs = db.count_jobs(conn)
    print(f"database: {open_jobs} open jobs, {closed_jobs} closed")


def _fetch(
    target: ScrapeTarget, sources: dict[str, Callable[[str, str], list[Job]]]
) -> list[Job]:
    fetch = sources.get(target.ats)
    if fetch is None:
        raise ValueError(f"unknown ats {target.ats!r}")
    return fetch(target.board, target.name)


def cmd_company_add(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if bool(args.ats) != bool(args.board):
        sys.exit("--ats and --board go together: give both or neither")
    try:
        employees_min, employees_max = parse_employees(args.employees)
    except ValueError as err:
        sys.exit(str(err))

    company = Company(
        name=args.name,
        ats=args.ats,
        board=args.board,
        website=args.website,
        career_site=args.career_site,
        description=args.description,
        tags=parse_csv(args.tags),
        employees_min=employees_min,
        employees_max=employees_max,
        company_type=args.company_type,
    )
    try:
        company_id = db.add_company(conn, company)
    except sqlite3.IntegrityError:
        sys.exit(f"{args.name} (or that ats + board) is already in the database")
    print(f"added {company.name} (id {company_id})")


def cmd_company_list(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    for c in db.list_companies(conn):
        board = f"{c.ats}/{c.board}" if c.ats else "-"
        tags = ",".join(c.tags) or "-"
        print(f"{c.id:>4}  {c.name:<20} {board:<24} {tags}")


def cmd_company_import_yc(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    print("downloading YC company list...")
    existing = {c.name.lower(): c for c in db.list_companies(conn)}
    added = updated = 0
    for company in yc_companies.fetch_companies(include_all=args.all):
        current = existing.get(company.name.lower())
        if current is None:
            company.id = db.add_company(conn, company)
            existing[company.name.lower()] = company
            added += 1
        else:
            _fill_missing(current, company)
            db.update_company(conn, current)
            updated += 1
    print(f"added {added} companies, updated {updated} existing ones")


def _fill_missing(current: Company, new: Company) -> None:
    current.website = current.website or new.website
    current.description = current.description or new.description
    current.employees_min = current.employees_min or new.employees_min
    current.employees_max = current.employees_max or new.employees_max
    current.company_type = current.company_type or new.company_type
    current.yc_slug = current.yc_slug or new.yc_slug
    current.tags += [t for t in new.tags if t not in current.tags]


def cmd_company_discover(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    todo = [c for c in db.list_companies(conn) if c.ats is None]
    if args.limit:
        todo = todo[: args.limit]
    print(f"looking up {len(todo)} companies...")

    found = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(discover.find_board, c.name, c.website): c for c in todo}
        for future in as_completed(futures):
            company = futures[future]
            try:
                result = future.result()
            except Exception as err:  # noqa: BLE001
                print(f"{company.name}: ERROR ({err})")
                continue
            if result is None:
                continue
            company.ats, company.board = result
            try:
                db.update_company(conn, company)
            except sqlite3.IntegrityError:
                print(
                    f"{company.name}: {company.ats}/{company.board} already belongs to another company"
                )
                continue
            found += 1
            print(f"{company.name}: {company.ats}/{company.board}")
    print(f"found {found} of {len(todo)}")


def cmd_search(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    query = SearchQuery(
        terms=args.terms,
        raw=args.raw,
        work_type=args.work_type,
        company_type=args.company_type,
        tag=args.tag,
        company=args.company,
        location=args.location,
        max_employees=args.max_employees,
        seniority=args.seniority,
        category=args.category,
        skill=args.skill,
        years=args.years,
        days=args.days,
        include_closed=args.closed,
        limit=args.limit,
    )
    try:
        rows = db.search_jobs(conn, query)
    except sqlite3.OperationalError as err:
        sys.exit(f"bad search: {err}")
    if not rows:
        print("no jobs found")
        return

    width = shutil.get_terminal_size().columns
    role_width = max(20, width - 6 - 5 - 18 - 22 - 10 - 5)
    for row in rows:
        posted = age(row["published"] or row["first_seen"])
        print(
            f"{row['id']:>6} {posted:>4}  {cut(row['company'], 18):<18} "
            f"{cut(row['role'], role_width):<{role_width}} "
            f"{cut(row['location'], 22):<22} {row['work_type'] or '':<9}"
        )
    print(f"\n{len(rows)} jobs (magstrel show <id> for details)")


def cmd_show(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    job = db.get_job(conn, args.id)
    if job is None:
        sys.exit(f"no job with id {args.id}")
    employees = format_employees(job["employees_min"], job["employees_max"])
    print(f"{job['role']}")
    print(
        f"{job['company_name']} | {job['location']} | {job['work_type'] or 'work type unknown'}"
    )
    print(
        f"posted {age(job['published'] or job['first_seen'])} ago | {job['official_posting_url']}"
    )
    print()
    print(f"about {job['company_name']}: {job['company_description'] or '-'}")
    print(f"  {job['company_type'] or '?'} | {employees} | {job['website'] or '-'}")
    print(f"  tags: {', '.join(json.loads(job['tags'])) or '-'}")
    if job["closed_at"]:
        print(f"\nCLOSED: no longer posted since {age(job['closed_at'])} ago")
    extras = [
        f"{label}: {job[key]}"
        for label, key in (("salary", "salary"), ("equity", "equity"), ("visa", "visa"))
        if job[key]
    ]
    if job["min_loe"] is not None:
        upper = f"-{job['max_loe']}" if job["max_loe"] else "+"
        extras.append(f"experience: {job['min_loe']}{upper} years")
    if extras:
        print("\n" + " | ".join(extras))
    level = " | ".join(
        f"{label}: {job[key]}"
        for label, key in (("level", "seniority"), ("category", "category"))
        if job[key]
    )
    if level:
        print(level)
    job_skills = json.loads(job["skills"])
    if job_skills:
        print(f"skills: {', '.join(job_skills)}")
    contacts = json.loads(job["recruiter_detail"])
    if contacts:
        print("\ncontacts:")
        for who, link in contacts.items():
            print(f"  {who}: {link or '-'}")
    print()
    print(job["description"] or "(no description)")


def cmd_open(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    job = db.get_job(conn, args.id)
    if job is None:
        sys.exit(f"no job with id {args.id}")
    webbrowser.open(job["official_posting_url"])
    print(f"opened {job['official_posting_url']}")


def cmd_enrich(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    todo = []
    for row in db.enrichment_state(conn, rules.METHOD):
        input_hash = rules.input_hash(row["role"], row["location"], row["description"])
        outdated = row["version"] is None or row["version"] < rules.VERSION
        if args.all or outdated or row["input_hash"] != input_hash:
            todo.append((row, input_hash))
    if not todo:
        print("everything is already enriched")
        return

    print(f"enriching {len(todo)} jobs with rules v{rules.VERSION}...")
    results = [
        (row["id"], input_hash, rules.enrich(row["role"], row["location"], row["description"]))
        for row, input_hash in todo
    ]
    db.save_enrichments(conn, rules.METHOD, rules.VERSION, results)

    for field_name in ("work_type", "seniority", "category", "min_loe", "salary", "visa", "skills"):
        filled = sum(1 for _, _, e in results if getattr(e, field_name))
        print(f"  {field_name:<10} found for {filled:>6} of {len(results)}")
