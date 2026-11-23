import argparse
import sqlite3
import sys
from typing import get_args

from magstrel import db
from magstrel.models import Company, CompanyType
from magstrel.sources import greenhouse, lever
from magstrel.utils import parse_csv, parse_employees

# ats name -> that source's fetch function
SOURCES = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="magstrel", description="Your own job database."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser(
        "migrate", help="apply pending database migrations"
    ).set_defaults(run=cmd_migrate)
    commands.add_parser(
        "scrape", help="fetch jobs from every scrapable company"
    ).set_defaults(run=cmd_scrape)

    company = commands.add_parser("company", help="manage companies")
    company_commands = company.add_subparsers(dest="company_command", required=True)

    add = company_commands.add_parser("add", help="add a company")
    add.add_argument("name")
    add.add_argument("--ats", choices=SOURCES, help="job board system it uses")
    add.add_argument("--board", help="its board name on that ats, e.g. stripe")
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
    if not targets:
        sys.exit("no scrapable companies yet, add one with: magstrel company add ...")

    for target in targets:
        fetch = SOURCES.get(target.ats)
        if fetch is None:
            print(f"{target.name}: SKIPPED (unknown ats {target.ats!r})")
            continue
        try:
            jobs = fetch(target.board, target.name)
        except Exception as err:  # noqa: BLE001
            print(f"{target.name}: FAILED ({err})")
            continue
        new = db.save_jobs(conn, target.company_id, jobs)
        print(f"{target.name}: {len(jobs)} fetched, {new} new")
    print(f"total in database: {db.count_jobs(conn)}")


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

