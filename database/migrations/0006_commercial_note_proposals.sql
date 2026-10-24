-- Persist human-reviewed commercial notes without changing the immutable baseline.
-- Only explicit owner approval can publish into an IA Library working copy.
CREATE TABLE commercial_note_proposals (
 id UUID PRIMARY KEY,
 audio_id UUID NOT NULL REFERENCES audio_records(id),
 audio_version INTEGER NOT NULL,
 document_path TEXT NOT NULL,
 document_sha256 TEXT NOT NULL,
 customer_heading TEXT NOT NULL,
 customer_start INTEGER NOT NULL,
 customer_stop INTEGER NOT NULL,
 note_date TEXT NOT NULL,
 note_text TEXT NOT NULL,
 note_digest TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending'
     CHECK (status IN ('pending','executing','approved','rejected','expired','uncertain','failed')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
 resolved_at TIMESTAMPTZ,
 resolved_by TEXT,
 backup_reference TEXT,
 error_code TEXT
);
CREATE UNIQUE INDEX commercial_note_prevent_replay
 ON commercial_note_proposals (audio_id, note_digest)
 WHERE status IN ('pending','executing','approved','uncertain');
CREATE INDEX commercial_note_expiry ON commercial_note_proposals (status,expires_at);
