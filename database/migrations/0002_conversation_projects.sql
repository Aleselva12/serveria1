-- Add Chat projects without modifying the immutable 0001 baseline.
CREATE TABLE IF NOT EXISTS conversation_projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
    shared_context TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS project_id UUID
    REFERENCES conversation_projects(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_project
    ON conversations(project_id, updated_at DESC);
