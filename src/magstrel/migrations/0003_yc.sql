ALTER TABLE companies ADD COLUMN yc_slug TEXT;
CREATE UNIQUE INDEX companies_yc_slug ON companies (yc_slug);

ALTER TABLE jobs ADD COLUMN salary TEXT;
ALTER TABLE jobs ADD COLUMN equity TEXT;
ALTER TABLE jobs ADD COLUMN visa TEXT;
