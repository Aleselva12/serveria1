-- Advisory assessments shared by Roadmap, Home and Architecture.
CREATE TABLE roadmap_priority_evaluations (
    id UUID PRIMARY KEY,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX roadmap_priority_evaluations_latest ON roadmap_priority_evaluations(created_at DESC);
