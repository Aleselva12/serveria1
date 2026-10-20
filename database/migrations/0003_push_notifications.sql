-- Calendar reminders and Web Push subscriptions.
ALTER TABLE calendar_events
    ADD COLUMN IF NOT EXISTS reminder_minutes INTEGER DEFAULT 30
    CHECK (reminder_minutes IS NULL OR reminder_minutes BETWEEN 1 AND 10080);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id UUID PRIMARY KEY,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT 'Dispositivo',
    user_agent TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_success_at TIMESTAMPTZ,
    last_attempt_at TIMESTAMPTZ,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_active
    ON push_subscriptions(active, updated_at DESC);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id UUID PRIMARY KEY,
    subscription_id UUID NOT NULL REFERENCES push_subscriptions(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
    event_version INTEGER NOT NULL,
    kind TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL,
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(subscription_id, event_id, kind, scheduled_for)
);
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_event
    ON notification_deliveries(event_id, event_version);
