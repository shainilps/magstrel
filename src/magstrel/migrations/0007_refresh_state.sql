-- when discovery last looked for this company's job board (found or not)
ALTER TABLE companies ADD COLUMN ats_checked_at TEXT;

-- every company without a board was checked by the discovery run a few days ago
UPDATE companies SET ats_checked_at = strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now') WHERE ats IS NULL;

-- small key/value store for refresh status: last runs, current step, server url ...
CREATE TABLE app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
