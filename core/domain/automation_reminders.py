"""Schedule and dispatch owner notifications created by automation runs."""
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5


def schedule(run, node_id, title, deliver_at):
    from core.infra.database import db_connection

    identifier = uuid5(NAMESPACE_URL, f"cora:reminder:{run['draft_id']}:{node_id}:{deliver_at.isoformat()}")
    with db_connection() as conn:
        conn.execute("""INSERT INTO app_notifications
            (id, created_at, source, kind, severity, title, url, ref)
            VALUES (%s, %s, 'automation', 'reminder', 'info', %s, '/#automations', %s)
            ON CONFLICT (id) DO NOTHING""", (identifier, deliver_at, title, run["id"]))
    return str(identifier)


def deliver_due(now):
    from core.domain import notifications
    from core.infra.database import db_connection

    with db_connection() as conn:
        rows = conn.execute("""UPDATE app_notifications SET pushed_at=%s
            WHERE source='automation' AND kind='reminder' AND pushed_at IS NULL
              AND dismissed_at IS NULL AND created_at<=%s
            RETURNING id, title, created_at, url""", (now, now)).fetchall()
    fresh = [row for row in rows if row["created_at"] > now - timedelta(minutes=5)]
    if not fresh:
        return
    subscriptions = notifications._active_subscriptions()
    for row in fresh:
        for subscription in subscriptions:
            notifications.send_one(subscription, {
                "title": row["title"], "body": "Promemoria programmato da Cora",
                "url": row["url"], "tag": f"automation-{row['id']}",
            }, ttl=300)
