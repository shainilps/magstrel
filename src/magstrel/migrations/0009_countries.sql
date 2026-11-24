-- country codes and regions ("in", "apac", "anywhere") read from the location text:
-- countries = every place it names, remote_countries = where a remote hire may live
ALTER TABLE job_enrichment ADD COLUMN countries TEXT NOT NULL DEFAULT '[]';
ALTER TABLE job_enrichment ADD COLUMN remote_countries TEXT NOT NULL DEFAULT '[]';

DROP VIEW job_view;

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
    COALESCE(llm.category, rules.category) AS category,
    COALESCE(NULLIF(llm.countries, '[]'), rules.countries, '[]') AS countries,
    COALESCE(NULLIF(llm.remote_countries, '[]'), rules.remote_countries, '[]') AS remote_countries
FROM jobs j
LEFT JOIN job_enrichment rules ON rules.job_id = j.id AND rules.method = 'rules'
LEFT JOIN job_enrichment llm ON llm.job_id = j.id AND llm.method = 'llm';
