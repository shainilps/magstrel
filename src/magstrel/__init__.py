from magstrel.sources import greenhouse


def main() -> None:
    boards = ["stripe", "airbnb", "cloudflare"]
    for board in boards:
        jobs = greenhouse.fetch(board)
        for job in jobs:
            print(f"{job.role} — {job.location}")
        print(f"{board}: {len(jobs)} jobs\n")
