CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Nuova chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    transcript_path TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id TEXT,
    model_id TEXT,
    parent_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    embedding VECTOR,
    embedding_model TEXT,
    embedding_dimensions INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON messages(conversation_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY,
    memory_type TEXT NOT NULL,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    importance SMALLINT NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    embedding VECTOR,
    embedding_model TEXT,
    embedding_dimensions INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(memory_type, key)
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC);

CREATE TABLE IF NOT EXISTS memory_relations (
    id UUID PRIMARY KEY,
    source_memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    target_memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(source_memory_id, target_memory_id, relation_type)
);

CREATE TABLE IF NOT EXISTS agent_events (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    component TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    thread_id TEXT,
    duration_ms DOUBLE PRECISION,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_agent_events_timestamp
    ON agent_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_events_thread
    ON agent_events(thread_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_events_component
    ON agent_events(component, timestamp DESC);


CREATE TABLE IF NOT EXISTS system_context (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    content TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO system_context (id, content)
VALUES (1, '')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS episodes (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    episode_type TEXT NOT NULL DEFAULT 'conversation',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id TEXT,
    importance SMALLINT NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_episodes_created
    ON episodes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_conversation
    ON episodes(conversation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS working_memory (
    agent_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    PRIMARY KEY (agent_id, thread_id)
);

CREATE INDEX IF NOT EXISTS idx_working_memory_updated
    ON working_memory(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_working_memory_expires
    ON working_memory(expires_at);


CREATE TABLE IF NOT EXISTS memory_sources (
    id UUID PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_memory_sources_memory
    ON memory_sources(memory_id, created_at DESC);

-- Calendar is authoritative operational data, independent of semantic memory.
CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 200),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL CHECK (end_at > start_at),
    all_day BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_calendar_interval ON calendar_events(start_at, end_at);
CREATE TABLE IF NOT EXISTS calendar_event_history (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES calendar_events(id),
    action TEXT NOT NULL CHECK (action IN ('create','update','delete','restore')),
    actor TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calendar_history ON calendar_event_history(event_id, changed_at);
CREATE TABLE IF NOT EXISTS calendar_proposals (
    id UUID PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('create','update','delete')),
    event_id UUID REFERENCES calendar_events(id),
    expected_version INTEGER,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    CHECK (action = 'create' OR (event_id IS NOT NULL AND expected_version IS NOT NULL))
);


-- Generic owner approvals for CONFIRM policies outside domain-specific stores.
CREATE TABLE IF NOT EXISTS approval_requests (
    id UUID PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected','consumed','expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    consumed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status
    ON approval_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_requests_actor
    ON approval_requests(actor, created_at DESC);

-- Persistent lifecycle separate from the technical trace stream.
CREATE TABLE IF NOT EXISTS runtime_runs (
    id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'chat',
    target TEXT NOT NULL DEFAULT 'supervisor',
    parent_run_id UUID REFERENCES runtime_runs(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','running','waiting_approval','completed','failed','cancelled','timed_out')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    error_type TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_runtime_runs_created
    ON runtime_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runtime_runs_thread
    ON runtime_runs(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runtime_runs_status
    ON runtime_runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS app_users (
 id UUID PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_sessions (
 token_hash TEXT PRIMARY KEY, user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON app_sessions(expires_at);
CREATE TABLE IF NOT EXISTS tool_policies (
 actor TEXT NOT NULL, action TEXT NOT NULL, policy TEXT NOT NULL CHECK(policy IN ('auto','confirm','blocked')),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY(actor,action)
);
CREATE TABLE IF NOT EXISTS action_approvals (
 id UUID PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, tool_id TEXT NOT NULL,
 payload JSONB NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW()+INTERVAL '24 hours',
 resolved_at TIMESTAMPTZ, resolved_by TEXT, error_type TEXT
);
CREATE TABLE IF NOT EXISTS conversation_summaries (
 conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
 through_message_id UUID NOT NULL, content TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE action_approvals ADD COLUMN IF NOT EXISTS result JSONB;

ALTER TABLE action_approvals ADD COLUMN IF NOT EXISTS actions JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE action_approvals ADD COLUMN IF NOT EXISTS tool_revision TEXT;

ALTER TABLE runtime_runs DROP CONSTRAINT IF EXISTS runtime_runs_status_check;
ALTER TABLE runtime_runs ADD CONSTRAINT runtime_runs_status_check CHECK
(status IN ('queued','running','waiting_approval','awaiting_approval','cancelling','completed','failed','cancelled','timed_out','interrupted'));
