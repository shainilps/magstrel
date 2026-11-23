from magstrel import db
from magstrel.sources import greenhouse


def main() -> None:
    boards = ["stripe", "airbnb", "cloudflare"]
    conn = db.connect()
    try:
        for board in boards:
            jobs = greenhouse.fetch(board)
            new = db.save_jobs(conn, jobs)
            print(f"{board}: {len(jobs)} fetched, {new} new")
        print(f"total in database: {db.count_jobs(conn)}")
    finally:
        conn.close()
