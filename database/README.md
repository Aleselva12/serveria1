# Cora persistence

Cora uses PostgreSQL with the pgvector extension as the authoritative persistent store.

Stored in PostgreSQL:

- conversations and messages;
- semantic embeddings for messages and memories;
- consolidated memories and their relations;
- transactional critical facts (`domain_events`, ordered by `domain_event_clock`) and bounded-retention metadata diagnostics (`diagnostic_events`);
- JSONB metadata for conversations, messages, memories and events.

Human-readable chat transcripts are generated under `CORA_CHAT_TRANSCRIPT_ROOT`.
The Markdown files are derived copies: PostgreSQL remains the authoritative source and transcripts can be regenerated.

## Local/server startup

1. Copy `.env.example` to `.env` and change database credentials.
2. Start PostgreSQL:
   `docker compose -f docker-compose.database.yml up -d`
3. Ensure the local embedding model configured by `CORA_EMBEDDING_MODEL` is installed in Ollama.
4. Start Cora normally.

The backend applies `database/schema.sql` as `0001_baseline`, then numbered SQL migrations, under an advisory lock with transactional SHA-256 registration. Applied files are not replayed and changed checksums stop startup. See [migration rules](migrations/README.md).

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

Le sintesi incrementali usano `conversation_summaries.through_message_id`; `context_jobs` conserva le conversazioni da preparare durante l’inattività. Sono dati derivati: i messaggi originali restano la fonte.

Memory edits are versioned in `memory_versions`, with an optimistic expected version and transactional key/row locks. Owner/legacy memories remain protected against unapproved agent updates. Existing classifications are unknown, not inferred during migration. `system_context_versions` preserves owner settings revisions. Memory embeddings are derived asynchronously and applied only to the indexed version. Memory deletion cascades to its revisions and source rows; this does not delete separate conversation/run archives.

## Current persistence boundary

Migrations 0002–0006 add chat attachments/audio/file-share metadata, consultation history, push subscriptions, conversation projects and commercial Word proposals. Runtime runs, capability operations, approvals and memory/context revisions are also persistent SQL state. Inspect `schema.sql` and each migration for the exact table/column contract; do not treat this list as an alternate schema.

SQL does not contain all application data: source audio, attachments, IA Library copies/originals, generated documents and updater workspaces/backups also need their filesystem storage. Runtime/model settings are JSON state, not SQL. Ollama model weights and external NAS mounts are outside the base Cora backup.

The local database Compose publishes its database port on host interfaces by default; it is a development profile. Use private network/firewall controls and changed credentials, or the server Compose with no published PostgreSQL port. Password sessions last seven days; desktop and Tailscale authentication are distinct modes.

Audit 25 October 2026: schema/migrator and callers inspected; integration tests are configured in `.github/workflows/verify.yml`, but queued CI is not a successful result. No production database or Debian migration was accessed. See [audit evidence](../docs/README_AUDIT_20261025.md).
