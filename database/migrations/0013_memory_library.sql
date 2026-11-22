CREATE TABLE memory_cards (
    id UUID PRIMARY KEY,
    scope TEXT NOT NULL,
    slug TEXT NOT NULL,
    current_version INTEGER NOT NULL CHECK (current_version > 0),
    UNIQUE (scope, slug)
);

CREATE TABLE memory_card_versions (
    card_id UUID NOT NULL REFERENCES memory_cards(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    document JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (card_id, version)
);

ALTER TABLE memory_cards ADD CONSTRAINT memory_cards_current_revision
    FOREIGN KEY (id, current_version) REFERENCES memory_card_versions(card_id, version)
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX messages_evidence_run_idx
    ON messages (conversation_id, (metadata->>'run_id'), created_at, id)
    WHERE role IN ('user', 'assistant');

CREATE INDEX episodes_evidence_run_idx
    ON episodes ((metadata->>'run_id'), created_at DESC)
    WHERE metadata ? 'run_id';
