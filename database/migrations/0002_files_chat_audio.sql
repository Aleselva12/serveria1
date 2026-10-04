CREATE TABLE file_shares (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token_hash TEXT UNIQUE NOT NULL,
 area TEXT NOT NULL, root_id TEXT NOT NULL, path TEXT NOT NULL, fingerprint TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ NOT NULL, revoked BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE chat_attachments (
 id UUID PRIMARY KEY, conversation_id UUID NOT NULL REFERENCES conversations(id),
 name TEXT NOT NULL, storage_path TEXT NOT NULL, size_bytes BIGINT NOT NULL, sha256 TEXT NOT NULL,
 extracted_text TEXT NOT NULL DEFAULT '', truncated BOOLEAN NOT NULL DEFAULT FALSE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX chat_attachments_conversation ON chat_attachments(conversation_id);
CREATE TABLE audio_records (
 id UUID PRIMARY KEY, title TEXT NOT NULL, name TEXT NOT NULL, source_path TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT '', speaker_names JSONB NOT NULL DEFAULT '[]',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), run_id UUID,
 transcript TEXT, machine_result JSONB, version INTEGER NOT NULL DEFAULT 1,
 archived BOOLEAN NOT NULL DEFAULT FALSE
);
