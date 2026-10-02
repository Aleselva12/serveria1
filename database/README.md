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

Application access is protected by an owner account and revocable seven-day sessions.
Provision/reset it interactively with `python -m core.auth`; credentials are hashed with
scrypt, session tokens are stored only as SHA-256 hashes. The schema also stores tool
policy overrides, exact generic action approvals and derived conversation summaries.
The connection pool defaults to 1–4 connections, with bounded waiting and SQL timeouts.
Messages are persisted first and indexed by the idle background worker; a failed index
does not erase source text. SQLite is not used.

Test URLs must point to a disposable database: the integration tests truncate tables.
For a PostgreSQL-protocol emulator that does not support prepared statements, set
`CORA_DB_PREPARE_THRESHOLD=none`; ordinary PostgreSQL defaults to threshold 5.
