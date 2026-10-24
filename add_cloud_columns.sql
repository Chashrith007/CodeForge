ALTER TABLE submissions
ADD COLUMN IF NOT EXISTS cloud_started_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS submissions_created_at_idx
ON submissions (created_at);
