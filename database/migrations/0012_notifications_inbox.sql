-- In-app notifications (Home window and Notifiche page) and health alert state.
-- A notification stays until the owner marks it as seen (dismissed_at).
CREATE TABLE app_notifications (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'success')),
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    url TEXT,
    ref TEXT,
    commit_sha TEXT NOT NULL DEFAULT '',
    pushed_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ
);
CREATE INDEX app_notifications_recent ON app_notifications(created_at DESC);
CREATE INDEX app_notifications_open ON app_notifications(created_at DESC) WHERE dismissed_at IS NULL;

-- One row per check: OK/failing, consecutive failures and whether the owner was told.
CREATE TABLE health_alert_state (
    check_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (state IN ('ok', 'failing')),
    fail_streak INTEGER NOT NULL DEFAULT 0,
    notified BOOLEAN NOT NULL DEFAULT FALSE,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_alert_at TIMESTAMPTZ
);
