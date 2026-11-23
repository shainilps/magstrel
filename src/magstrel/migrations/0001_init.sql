CREATE TABLE IF NOT EXISTS jobs (
    id                   INTEGER PRIMARY KEY,
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
    company_type         TEXT,
    skills               TEXT NOT NULL DEFAULT '[]',
    meta                 TEXT NOT NULL DEFAULT '[]',
    recruiter_detail     TEXT NOT NULL DEFAULT '{}',

    raw                  TEXT NOT NULL,

    first_seen           TEXT NOT NULL,
    last_seen            TEXT NOT NULL,

    UNIQUE (source, external_id)
);
