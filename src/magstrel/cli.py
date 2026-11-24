import argparse
import json
import logging
import shutil
import sqlite3
import sys
import webbrowser
from datetime import UTC, datetime, timedelta
from typing import get_args

import uvicorn

from magstrel import daemon, db, mcp_server, refresh
from magstrel.models import (
    Category,
    Company,
    CompanyType,
    SearchQuery,
    Seniority,
    WorkType,
)
from magstrel.utils import (
    age,
    cut,
    format_employees,
    parse_csv,
    parse_duration,
    parse_employees,
    until,
)
from magstrel.web import app as web_app

DEFAULT_EVERY = "24h"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="magstrel", description="Your own job database."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    up = commands.add_parser(
        "up", help="start web page + MCP + auto refresh in the background"
    )
    _server_options(up)
    up.set_defaults(run=cmd_up)
    commands.add_parser("down", help="stop the background server").set_defaults(
        run=cmd_down
    )
    commands.add_parser(
        "status", help="is it running, what is it doing, when did things last run"
    ).set_defaults(run=cmd_status)
    server = commands.add_parser(
        "server", help="what `up` runs, but in the foreground (Ctrl+C to stop)"
    )
    _server_options(server)
    server.set_defaults(run=cmd_server)

    commands.add_parser(
        "migrate", help="apply pending database migrations"
    ).set_defaults(run=cmd_migrate)
    scrape = commands.add_parser(
        "scrape", help="fetch jobs from every scrapable company"
    )
    scrape.add_argument("--workers", type=int, default=8, help="parallel downloads")
    scrape.add_argument(
        "--only",
        choices=[*refresh.SOURCES, "yc", "hn"],
        help="scrape just one source, e.g. --only yc",
    )
    scrape.set_defaults(run=cmd_scrape)

    company = commands.add_parser("company", help="manage companies")
    company_commands = company.add_subparsers(dest="company_command", required=True)

    add = company_commands.add_parser("add", help="add a company")
    add.add_argument("name")
    add.add_argument("--ats", choices=refresh.SOURCES, help="job board system it uses")
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
    find.add_argument(
        "--all",
        action="store_true",
        help="also recheck companies looked up in the last 30 days",
    )
    find.set_defaults(run=cmd_company_discover)

    verify = company_commands.add_parser(
        "verify", help="list companies whose linked job board may belong to someone else"
    )
    verify.add_argument("name", nargs="?", help="check just this company")
    verify.set_defaults(run=cmd_company_verify)
    unlink = company_commands.add_parser(
        "unlink", help="forget a company's job board (a wrong match) and close its jobs"
    )
    unlink.add_argument("name")
    unlink.set_defaults(run=cmd_company_unlink)

    enrich = commands.add_parser(
        "enrich", help="work out seniority, category, skills, ... from each job's text"
    )
    enrich.add_argument(
        "--all", action="store_true", help="redo every job, not just new ones"
    )
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
        "--remote-from", help="your country, e.g. India: remote jobs you can take from there"
    )
    search.add_argument(
        "--years", type=int, help="your years of experience: hide jobs asking for more"
    )
    search.add_argument(
        "--closed", action="store_true", help="also show jobs that are no longer posted"
    )
    search.add_argument("--limit", type=int, default=30)
    search.set_defaults(run=cmd_search)

    commands.add_parser(
        "mcp", help="MCP over stdio, for when `up` isn't running (Claude Code starts it)"
    ).set_defaults(run=cmd_mcp)

    show = commands.add_parser("show", help="show one job in full")
    show.add_argument("id", type=int)
    show.set_defaults(run=cmd_show)

    open_ = commands.add_parser("open", help="open a job posting in your browser")
    open_.add_argument("id", type=int)
    open_.set_defaults(run=cmd_open)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    conn = db.connect()
    try:
        if db.pending_migrations(conn):
            if args.command not in ("migrate", "down", "status"):
                sys.exit("database is out of date, run: magstrel migrate")
            if args.command == "status":
                print("(database has pending migrations: run `magstrel migrate`)")
        args.run(conn, args)
    finally:
        conn.close()


def _server_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--every", default=DEFAULT_EVERY, help="how often to refresh, e.g. 30m, 6h, 1d"
    )
    parser.add_argument(
        "--no-refresh", action="store_true", help="web page + MCP only, no auto refresh"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="127.0.0.1 = only this computer"
    )
    parser.add_argument("--port", type=int, default=8000)


def cmd_up(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if pid := daemon.running_pid():
        sys.exit(f"already running (pid {pid}), see: magstrel status")
    _check_every(args.every)
    url = f"http://{args.host}:{args.port}"
    server_args = ["--every", args.every, "--host", args.host, "--port", str(args.port)]
    if args.no_refresh:
        server_args.append("--no-refresh")
    try:
        pid = daemon.start(server_args, url)
    except RuntimeError as err:
        sys.exit(str(err))
    state = db.get_state(conn)
    refresh_note = "off" if args.no_refresh else f"every {args.every}"
    print(f"magstrel is up (pid {pid})")
    print(f"  web page:  {url}")
    print(f"  MCP:       {url}/mcp")
    print(f"  refresh:   {refresh_note}")
    print(f"  log:       {daemon.log_file()}")
    print()
    print("data:")
    print(f"  last full refresh:  {_ago(state.get('last_run_finished_at'))}")
    print(f"  jobs scraped:       {_ago(state.get('jobs_scraped_at'))}")
    print(f"  companies imported: {_ago(state.get('companies_imported_at'))}")
    open_jobs, _ = db.count_jobs(conn)
    print(f"  open jobs:          {open_jobs:,}")
    if not args.no_refresh and _is_stale(state.get("last_run_finished_at"), args.every):
        print("  (a refresh is starting now in the background)")
    print()
    print("connect Claude Code (once):")
    print(f"  claude mcp add --transport http --scope user magstrel {url}/mcp")
    print()
    print("see progress: magstrel status   ·   stop: magstrel down")


def cmd_down(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    pid = daemon.stop()
    print(f"stopped (pid {pid})" if pid else "not running")


def cmd_server(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    every = None if args.no_refresh else _check_every(args.every)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True
    )
    db.set_state(
        conn,
        server_url=f"http://{args.host}:{args.port}",
        refresh_every=None if every is None else args.every,
    )
    conn.close()
    web_app.app.state.refresh_every = every
    uvicorn.run(web_app.app, host=args.host, port=args.port)


def cmd_status(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    state = db.get_state(conn)
    pid = daemon.running_pid()
    url = state.get("server_url", "?")

    if pid:
        print(f"running (pid {pid}) at {url}   ·   MCP: {url}/mcp")
        if state.get("refresh_status") == "running":
            started = age(state.get("last_run_started_at"))
            print(f"now:           {state.get('current_step')}  (refresh started {started} ago)")
        elif state.get("refresh_every"):
            print(f"now:           idle, next refresh in {until(state.get('next_run_at'))}")
        else:
            print("now:           idle (auto refresh is off)")
    else:
        print("not running (start it with: magstrel up)")

    finished = state.get("last_run_finished_at")
    if finished:
        took = _duration(state.get("last_run_started_at"), finished)
        print(f"last refresh:  finished {age(finished)} ago, {state.get('last_run_result')}, took {took}")
    else:
        print("last refresh:  never")
    print(
        f"companies:     YC list imported {_ago(state.get('companies_imported_at'))}"
        f" · job boards checked {_ago(state.get('boards_checked_at'))}"
    )
    print(
        f"jobs:          scraped {_ago(state.get('jobs_scraped_at'))}"
        f" · enriched {_ago(state.get('enriched_at'))}"
    )
    if state.get("refresh_every"):
        print(f"schedule:      every {state['refresh_every']}")
    open_jobs, closed_jobs = db.count_jobs(conn)
    print(
        f"database:      {open_jobs:,} open jobs, {closed_jobs:,} closed"
        f" · {db.count_companies(conn):,} companies"
    )


def _is_stale(last: str | None, every: str) -> bool:
    if last is None:
        return True
    return datetime.fromisoformat(last) + parse_duration(every) <= datetime.now(UTC)


def _ago(iso: str | None) -> str:
    return f"{age(iso)} ago" if iso else "never"


def _duration(start: str | None, end: str) -> str:
    if not start:
        return "?"
    seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def _check_every(text: str) -> timedelta:
    try:
        return parse_duration(text)
    except ValueError as err:
        sys.exit(str(err))


def cmd_migrate(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    applied = db.migrate(conn)
    for name in applied:
        print(f"applied {name}")
    if not applied:
        print("already up to date")


def cmd_scrape(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if not refresh.scrape_jobs(conn, only=args.only, workers=args.workers):
        sys.exit("nothing to scrape, add companies with: magstrel company add ...")


def cmd_enrich(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    refresh.enrich_jobs(conn, force=args.all)


def cmd_company_import_yc(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    refresh.import_yc(conn, include_all=args.all)


def cmd_company_discover(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    refresh.discover_boards(
        conn, limit=args.limit, workers=args.workers, recheck_all=args.all
    )


def cmd_company_verify(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if refresh.verify_boards(conn, company=args.name):
        print('check those boards, then unlink wrong ones with: magstrel company unlink "NAME"')


def cmd_company_unlink(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if refresh.unlink_company(conn, args.name) is None:
        sys.exit(f"no company named {args.name!r}")


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
        remote_from=args.remote_from,
        include_closed=args.closed,
        limit=args.limit,
    )
    try:
        rows = db.search_jobs(conn, query)
    except (sqlite3.OperationalError, ValueError) as err:
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


def cmd_mcp(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    conn.close()
    mcp_server.server.run("stdio")


def cmd_open(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    job = db.get_job(conn, args.id)
    if job is None:
        sys.exit(f"no job with id {args.id}")
    webbrowser.open(job["official_posting_url"])
    print(f"opened {job['official_posting_url']}")
