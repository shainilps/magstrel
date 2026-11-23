import argparse
import sqlite3
import sys

from magstrel import db
from magstrel.sources import greenhouse, lever

# source name -> that source's fetch function
SOURCES = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
}

# (source, board, display name). Temporary: moves to companies.toml next.
COMPANIES = [
    ("greenhouse", "stripe", "Stripe"),
    ("greenhouse", "airbnb", "Airbnb"),
    ("greenhouse", "cloudflare", "Cloudflare"),
    ("lever", "palantir", "Palantir"),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="magstrel", description="Your own job database."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "migrate", help="apply pending database migrations"
    ).set_defaults(run=cmd_migrate)
    commands.add_parser("scrape", help="fetch jobs from all companies").set_defaults(
        run=cmd_scrape
    )
    args = parser.parse_args()

    conn = db.connect()
    try:
        args.run(conn)
    finally:
        conn.close()


def cmd_migrate(conn: sqlite3.Connection) -> None:
    applied = db.migrate(conn)
    for name in applied:
        print(f"applied {name}")
    if not applied:
        print("already up to date")


def cmd_scrape(conn: sqlite3.Connection) -> None:
    if db.pending_migrations(conn):
        sys.exit("database is out of date, run: magstrel migrate")

    for source, board, name in COMPANIES:
        fetch = SOURCES[source]
        try:
            jobs = fetch(board, name)
        except Exception as err:
            print(f"{name}: FAILED ({err})")
            continue
        new = db.save_jobs(conn, jobs)
        print(f"{name}: {len(jobs)} fetched, {new} new")
    print(f"total in database: {db.count_jobs(conn)}")
