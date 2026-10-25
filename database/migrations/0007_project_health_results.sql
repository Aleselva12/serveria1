-- Append-only results for one canonical check catalog; no user contents or secrets.
CREATE TABLE project_health_results (
 id BIGSERIAL PRIMARY KEY,
 check_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK (status IN ('pass','fail','unknown','skipped')),
 detail TEXT NOT NULL DEFAULT '',
 source TEXT NOT NULL CHECK (source IN ('periodic','manual','ci','updater')),
 environment TEXT NOT NULL,
 commit_sha TEXT NOT NULL DEFAULT '',
 duration_ms INTEGER NOT NULL DEFAULT 0,
 observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX project_health_latest ON project_health_results(check_id,observed_at DESC,id DESC);
CREATE INDEX project_health_observed ON project_health_results(observed_at DESC);
