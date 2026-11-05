-- Durable progress for owner-initiated, one-shot verification from the website.
CREATE TABLE node_verification_runs (
    id UUID PRIMARY KEY,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX node_verification_runs_latest ON node_verification_runs(created_at DESC);
