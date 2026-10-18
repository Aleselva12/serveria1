-- Private, content-free evidence; removed together with its conversation.
CREATE TABLE chat_consultations (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    run_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kind TEXT NOT NULL CHECK (kind IN ('tool','file','context')),
    name TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE INDEX chat_consultations_page ON chat_consultations(conversation_id,id DESC);
