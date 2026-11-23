CREATE TABLE profiles (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    about      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

-- one row per (profile, job): its current status
CREATE TABLE applications (
    id         INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles (id) ON DELETE CASCADE,
    job_id     INTEGER NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    status     TEXT NOT NULL,
    applied_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (profile_id, job_id)
);

-- every status change, with its date and note: the history
CREATE TABLE application_events (
    id             INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    status         TEXT NOT NULL,
    note           TEXT NOT NULL DEFAULT '',
    at             TEXT NOT NULL
);

CREATE INDEX application_events_application ON application_events (application_id);
