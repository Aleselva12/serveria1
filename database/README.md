# Cora persistence

Cora uses PostgreSQL with the pgvector extension as the authoritative persistent store.

Stored in PostgreSQL:
- conversations and messages;
- semantic embeddings for messages and memories;
- consolidated memories and their relations;
- structured agent/runtime events;
- JSONB metadata for conversations, messages, memories and events.

Human-readable chat transcripts are generated under `CORA_CHAT_TRANSCRIPT_ROOT`.
The Markdown files are derived copies: PostgreSQL remains the authoritative source and transcripts can be regenerated.

## Local/server startup

1. Copy `.env.example` to `.env` and change database credentials.
2. Start PostgreSQL:
   `docker compose -f docker-compose.database.yml up -d`
3. Ensure the local embedding model configured by `CORA_EMBEDDING_MODEL` is installed in Ollama.
4. Start Cora normally.

The schema is applied idempotently by the backend from `database/schema.sql`.
