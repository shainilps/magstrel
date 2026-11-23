CREATE TABLE companies (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL UNIQUE,
    website              TEXT,
    career_site          TEXT,
    description          TEXT NOT NULL DEFAULT '',
    tags                 TEXT NOT NULL DEFAULT '[]',
    employees_min        INTEGER,
    employees_max        INTEGER,
    company_type         TEXT,

    ats                  TEXT,
    board                TEXT,

    added_at             TEXT NOT NULL,

    UNIQUE (ats, board)
);

CREATE TABLE jobs (
    id                   INTEGER PRIMARY KEY,
    company_id           INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
    source               TEXT NOT NULL,
    external_id          TEXT NOT NULL,
    company              TEXT NOT NULL,
    role                 TEXT NOT NULL,
    location             TEXT NOT NULL,
    official_posting_url TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    published            TEXT,
    deadline             TEXT,

    work_type            TEXT,
    min_loe              INTEGER,
    max_loe              INTEGER,
    skills               TEXT NOT NULL DEFAULT '[]',
    recruiter_detail     TEXT NOT NULL DEFAULT '{}',

    raw                  TEXT NOT NULL,

    first_seen           TEXT NOT NULL,
    last_seen            TEXT NOT NULL,

    UNIQUE (source, external_id)
);

CREATE INDEX jobs_company_id ON jobs (company_id);
