# magstrel (magpie+kestrel)

your own job database, scraped straight from company job boards.

## run

```
uv sync
uv run magstrel migrate
uv run magstrel up        # web + mcp + refresh every 24h, in the background
uv run magstrel status
uv run magstrel down
```

web page at http://127.0.0.1:8000, mcp at http://127.0.0.1:8000/mcp

## what it does

- pulls jobs from greenhouse, lever, ashby, recruitee, workable, smartrecruiters, yc and hn who is hiring
- imports yc companies and finds their job boards
- works out seniority, category, skills, years, salary, visa from the text
- tracks applications per profile

## mcp tools

- `search_jobs`, `get_job`, `list_companies`
- `create_profile`, `list_profiles`, `delete_profile`
- `track_application`, `list_applications`, `get_application`, `delete_application`, `profile_stats`
- `verify_company_boards`, `unlink_company_board`

## connect

```
claude mcp add --transport http --scope user magstrel http://127.0.0.1:8000/mcp
```
