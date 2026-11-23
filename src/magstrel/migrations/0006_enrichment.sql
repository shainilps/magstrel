CREATE TABLE job_enrichment (
    job_id      INTEGER NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    method      TEXT NOT NULL,
    version     INTEGER NOT NULL,
    input_hash  TEXT NOT NULL,
    enriched_at TEXT NOT NULL,

    work_type   TEXT,
    min_loe     INTEGER,
    max_loe     INTEGER,
    salary      TEXT,
    visa        TEXT,
    skills      TEXT NOT NULL DEFAULT '[]',
    seniority   TEXT,
    category    TEXT,

    PRIMARY KEY (job_id, method)
);

-- a fact from the source wins, then the llm, then the rules
CREATE VIEW job_view AS
SELECT
    j.id, j.company_id, j.source, j.external_id, j.company, j.role, j.location,
    j.official_posting_url, j.description, j.published, j.deadline, j.recruiter_detail,
    j.raw, j.first_seen, j.last_seen, j.equity, j.closed_at,
    COALESCE(j.work_type, llm.work_type, rules.work_type) AS work_type,
    COALESCE(j.min_loe, llm.min_loe, rules.min_loe) AS min_loe,
    COALESCE(j.max_loe, llm.max_loe, rules.max_loe) AS max_loe,
    COALESCE(j.salary, llm.salary, rules.salary) AS salary,
    COALESCE(j.visa, llm.visa, rules.visa) AS visa,
    COALESCE(NULLIF(j.skills, '[]'), NULLIF(llm.skills, '[]'), rules.skills, '[]') AS skills,
    COALESCE(llm.seniority, rules.seniority) AS seniority,
    COALESCE(llm.category, rules.category) AS category
FROM jobs j
LEFT JOIN job_enrichment rules ON rules.job_id = j.id AND rules.method = 'rules'
LEFT JOIN job_enrichment llm ON llm.job_id = j.id AND llm.method = 'llm';
