DROP TRIGGER jobs_fts_after_insert;
DROP TRIGGER jobs_fts_after_delete;
DROP TRIGGER jobs_fts_after_update;
DROP TABLE jobs_fts;

CREATE VIRTUAL TABLE jobs_fts USING fts5(
    role, company, location, description,
    content = 'jobs',
    content_rowid = 'id',
    tokenize = "porter unicode61 tokenchars '+#'"
);

CREATE TRIGGER jobs_fts_after_insert AFTER INSERT ON jobs BEGIN
    INSERT INTO jobs_fts (rowid, role, company, location, description)
    VALUES (new.id, new.role, new.company, new.location, new.description);
END;

CREATE TRIGGER jobs_fts_after_delete AFTER DELETE ON jobs BEGIN
    INSERT INTO jobs_fts (jobs_fts, rowid, role, company, location, description)
    VALUES ('delete', old.id, old.role, old.company, old.location, old.description);
END;

CREATE TRIGGER jobs_fts_after_update AFTER UPDATE ON jobs
WHEN old.role IS NOT new.role
  OR old.company IS NOT new.company
  OR old.location IS NOT new.location
  OR old.description IS NOT new.description
BEGIN
    INSERT INTO jobs_fts (jobs_fts, rowid, role, company, location, description)
    VALUES ('delete', old.id, old.role, old.company, old.location, old.description);
    INSERT INTO jobs_fts (rowid, role, company, location, description)
    VALUES (new.id, new.role, new.company, new.location, new.description);
END;

INSERT INTO jobs_fts (jobs_fts) VALUES ('rebuild');
