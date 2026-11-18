"""Health alerts: confirmed transitions, throttled pushes, quiet hours."""
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from core.domain import health_alerts as ha

T0 = datetime(2026, 11, 17, 11, 0, tzinfo=UTC)  # 12:00 in Rome


def run(statuses, needed=2, state=None, step=timedelta(minutes=5)):
    events = []
    for index, status in enumerate(statuses):
        state, event = ha.transition(state, status, needed, T0 + index * step)
        events.append(event)
    return state, events


class TransitionTests(unittest.TestCase):
    def test_periodic_failure_needs_two_in_a_row_then_recovery_is_announced(self):
        state, events = run(["pass", "fail", "pass", "fail", "fail", "fail", "pass"])
        self.assertEqual(events, [None, None, None, None, "failure", None, "recovery"])
        self.assertEqual((state["state"], state["fail_streak"]), ("ok", 0))

    def test_collaudi_alert_on_the_first_failure(self):
        self.assertEqual(run(["fail"], needed=1)[1], ["failure"])

    def test_inconclusive_results_change_nothing(self):
        state, events = run(["fail", "warn", "unknown", "skipped", "fail"])
        self.assertEqual(events, [None, None, None, None, "failure"])
        self.assertEqual(run(["unknown"])[0], None)

    def test_flapping_is_pushed_at_most_once_every_6_hours_and_silent_recovery_stays_silent(self):
        state, events = run(["fail", "fail", "pass", "fail", "fail", "pass"], step=timedelta(minutes=30))
        # The second outage comes 1h after the first alert: tracked but not announced,
        # so its recovery is not announced either.
        self.assertEqual(events, [None, "failure", "recovery", None, None, None])
        later = T0 + timedelta(hours=7)
        state, event = ha.transition(state, "fail", 1, later)
        self.assertEqual(event, "failure")

    def test_periodic_probes_need_confirmation_collaudi_do_not(self):
        self.assertEqual(ha.confirmations("database", "periodic"), 2)
        self.assertEqual(ha.confirmations("memory_regression", "nightly"), 1)
        self.assertEqual(ha.confirmations("immich_e2e", "manual"), 1)

    def test_quiet_hours_are_23_to_7_in_rome(self):
        def rome(hour):
            return datetime(2026, 11, 17, hour - 1, 30, tzinfo=UTC)  # CET
        self.assertEqual([ha.quiet(rome(h)) for h in (6, 7, 12, 22, 23)], [True, False, False, False, True])
        self.assertTrue(ha.quiet(datetime(2026, 11, 17, 23, 30, tzinfo=UTC)))  # 00:30 local


class ObserveTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.state = None
        def execute(sql, params=()):
            result = MagicMock()
            if sql.startswith("SELECT * FROM health_alert_state"):
                result.fetchone.return_value = self.state
            if "INSERT INTO health_alert_state" in sql:
                keys = ("check_id", "state", "fail_streak", "notified", "changed_at", "last_alert_at")
                self.state = dict(zip(keys, params, strict=True))
            return result
        self.conn.execute.side_effect = execute
        @contextmanager
        def connect():
            yield self.conn
        for target in (patch("core.infra.database.db_connection", connect), patch.object(ha, "wake")):
            target.start()
            self.addCleanup(target.stop)

    def row(self, status, minutes=0, environment="debian-verifier"):
        return {"id": "memory_regression", "status": status, "detail": "3 fallimenti", "commit": "b002be0abc",
                "environment": environment, "at": (T0 + timedelta(minutes=minutes)).isoformat()}

    def inserted(self):
        return [call.args[1] for call in self.conn.execute.call_args_list
                if call.args[0].lstrip().startswith("INSERT INTO app_notifications")]

    def test_failure_and_recovery_become_notifications_with_check_title_and_version(self):
        self.assertEqual(len(ha.observe([self.row("fail")], "nightly")), 1)
        self.assertEqual(len(ha.observe([self.row("pass", 60)], "manual")), 1)
        failure, recovery = self.inserted()
        self.assertEqual(failure[3:6], ("failure", "error", "Errore: Memoria e contratti contesto: regressioni"))
        self.assertIn("3 fallimenti · versione b002be0", failure[6])
        self.assertEqual(recovery[3:5], ("recovery", "success"))
        self.assertEqual(failure[7], "/#notifications")

    def test_results_from_ci_or_other_machines_are_ignored(self):
        self.assertEqual(ha.observe([self.row("fail", environment="ci-verifier")], "nightly"), [])
        self.assertEqual(self.inserted(), [])

    def test_a_database_failure_never_reaches_the_caller(self):
        self.conn.execute.side_effect = OSError("down")
        with self.assertLogs("cora.health_monitor", "WARNING"):
            self.assertEqual(ha.observe([self.row("fail")], "nightly"), [])


class DeliverTests(unittest.TestCase):
    def deliver(self, rows, now):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = rows
        @contextmanager
        def connect():
            yield conn
        with patch("core.infra.database.db_connection", connect), patch.object(ha, "_push") as push:
            count = ha.deliver(now)
        return count, push, conn

    def test_nothing_is_pushed_during_quiet_hours(self):
        count, push, conn = self.deliver([], datetime(2026, 11, 17, 3, 0, tzinfo=UTC))
        self.assertEqual(count, 0)
        conn.execute.assert_not_called()

    def test_overnight_alerts_become_one_morning_summary(self):
        def night(hour):
            return datetime(2026, 11, 17, hour, 0, tzinfo=UTC)
        rows = [{"id": i, "title": f"Errore: {i}", "body": "", "ref": str(i), "created_at": night(3 + i)}
                for i in range(2)] + [{"id": 9, "title": "Errore: giorno", "body": "x", "ref": "d", "created_at": night(7)}]
        count, push, _ = self.deliver(rows, night(7))
        self.assertEqual(count, 3)
        titles = [call.args[0]["title"] for call in push.call_args_list]
        self.assertEqual(titles, ["Cora · Collaudi della notte", "Cora · Errore: giorno"])
        self.assertIn("2 avvisi", push.call_args_list[0].args[0]["body"])

    def test_pending_rows_are_claimed_before_sending(self):
        _, _, conn = self.deliver([], T0)
        sql = conn.execute.call_args.args[0]
        self.assertIn("UPDATE app_notifications SET pushed_at", sql)
        self.assertIn("pushed_at IS NULL", sql)


class InboxApiTests(unittest.TestCase):
    def client(self, conn):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.api import inbox_api
        @contextmanager
        def connect():
            yield conn
        app = FastAPI()
        app.include_router(inbox_api.router)
        app.dependency_overrides[inbox_api.owner] = lambda: None
        patcher = patch("core.infra.database.db_connection", connect)
        patcher.start()
        self.addCleanup(patcher.stop)
        return TestClient(app)

    def test_list_mark_one_and_mark_all_seen(self):
        conn = MagicMock()
        row = {"id": "5f6c1a1e-0000-4000-8000-000000000001", "created_at": T0, "source": "health",
               "kind": "failure", "severity": "error", "title": "Errore: X", "body": "b", "url": "/#notifications",
               "ref": "x", "commit_sha": "abc", "dismissed_at": None}
        conn.execute.return_value.fetchall.return_value = [row]
        conn.execute.return_value.fetchone.side_effect = [{"n": 1}, {"id": row["id"]}, None]
        conn.execute.return_value.rowcount = 3
        client = self.client(conn)
        data = client.get("/api/v1/notifications/inbox").json()
        self.assertEqual((data["unseen"], data["items"][0]["title"], data["items"][0]["seenAt"]), (1, "Errore: X", None))
        self.assertIn("WHERE dismissed_at IS NULL", conn.execute.call_args_list[0].args[0])
        self.assertEqual(client.post(f"/api/v1/notifications/inbox/{row['id']}/seen").json(), {"seen": True})
        self.assertEqual(client.post(f"/api/v1/notifications/inbox/{row['id']}/seen").status_code, 404)
        self.assertEqual(client.post("/api/v1/notifications/inbox/seen").json(), {"seen": 3})
        self.assertEqual(client.post("/api/v1/notifications/inbox/not-a-uuid/seen").status_code, 422)



class TimelineTests(unittest.TestCase):
    def test_failing_now_comes_from_the_full_state_and_history_from_notifications(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [
            [{"check_id": "nextcloud_e2e", "fail_streak": 3, "changed_at": T0, "notified": False}],
            [{"id": "n1", "created_at": T0, "kind": "failure", "title": "Errore: Nextcloud", "body": "giù",
              "ref": "nextcloud_e2e", "commit_sha": "abc"}],
        ]
        @contextmanager
        def connect():
            yield conn
        with patch("core.infra.database.db_connection", connect):
            data = ha.timeline()
        self.assertEqual(data["failing"][0]["title"], "Nextcloud: raggiungibilità HTTP")
        self.assertEqual((data["failing"][0]["failures"], data["failing"][0]["notified"]), (3, False))
        self.assertEqual(data["history"][0]["checkId"], "nextcloud_e2e")
        self.assertIn("source='health'", conn.execute.call_args_list[1].args[0])

    def test_endpoint_reports_an_unavailable_database_as_503(self):
        from fastapi import HTTPException

        from core.verify import project_checks
        with patch.object(ha, "timeline", side_effect=OSError("down")):
            with self.assertRaises(HTTPException) as caught:
                project_checks.health_transitions()
        self.assertEqual(caught.exception.status_code, 503)

if __name__ == "__main__":
    unittest.main()
