import os
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import calendar as store
from core.calendar_api import router
from core.calendar_tools import calendar_tools_for
from core.permissions import check_permission, validate_permission_configuration

DATA = dict(title="Cliente", start="2026-10-02T09:00:00+02:00", end="2026-10-02T10:00:00+02:00", all_day=False, notes="Preventivo")


class CalendarValidationTests(unittest.TestCase):
    def test_title_timezone_interval_and_unknown_fields(self):
        for delta in ({"title":"   "}, {"start":"2026-10-02T09:00:00"},
                      {"end":DATA["start"]}, {"actor":"user"}, {"user_approved":True}):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                store.EventInput.model_validate({**DATA, **delta})

    def test_all_day_uses_italian_midnight_and_exclusive_end(self):
        event = store.EventInput.model_validate({**DATA,"all_day":True,
            "start":"2026-03-29T00:00:00+01:00","end":"2026-03-30T00:00:00+02:00"})
        self.assertEqual((event.end-event.start).total_seconds(),23*3600)
        with self.assertRaises(ValueError):
            store.EventInput.model_validate({**DATA,"all_day":True})

    def test_permissions_deny_unknown_actor_and_need_owner_approval(self):
        self.assertTrue(validate_permission_configuration()["valid"])
        self.assertFalse(check_permission("unknown", "calendar_create_event").allowed)
        self.assertFalse(check_permission("structure_agent", "calendar_create_event").allowed)
        self.assertTrue(check_permission("supervisor", "calendar_list_event").allowed)
        self.assertTrue(check_permission("supervisor", "calendar_create_event").requires_user_confirmation)
        with self.assertRaises(PermissionError):
            store.write_event("create", actor="supervisor", data=DATA)

    def test_tools_bind_identity_and_do_not_expose_approval(self):
        tools = {t.name:t for t in calendar_tools_for("email_quotes_agent")}
        self.assertEqual(len(tools),5)
        for tool in tools.values():
            self.assertNotIn("actor",tool.args)
            self.assertNotIn("user_approved",tool.args)
        with patch.object(store,"propose_event",return_value={"status":"pending","id":str(uuid4())}) as proposal, patch("core.operation_journal.begin",return_value=None):
            result = tools["calendar_create_event"].invoke(DATA)
            self.assertEqual(result["status"],"pending")
            self.assertEqual(proposal.call_args.args[:2],("email_quotes_agent","create"))

    def test_api_access_and_validation(self):
        app = FastAPI(); app.include_router(router)
        with patch.dict(os.environ,{"CORA_CALENDAR_TOKEN":"owner"}), TestClient(app) as client:
            self.assertEqual(client.get("/api/v1/calendar/proposals").status_code,401)
            with patch.object(store,"list_proposals",return_value=[]):
                self.assertEqual(client.get("/api/v1/calendar/proposals",headers={"Authorization":"Bearer owner"}).json(),[])
            headers={"Authorization":"Bearer owner"}
            self.assertEqual(client.post("/api/v1/calendar/events",json={**DATA,"actor":"user"},headers=headers).status_code,422)
            self.assertEqual(client.delete(f"/api/v1/calendar/events/{uuid4()}?version=0",headers=headers).status_code,422)
        with patch.dict(os.environ,{"CORA_CALENDAR_TOKEN":""}), TestClient(app) as client:
            self.assertEqual(client.get("/api/v1/calendar/proposals").status_code,403)


@unittest.skipUnless(os.getenv("CORA_CALENDAR_TEST_DATABASE_URL"), "Requires a dedicated disposable PostgreSQL test database")
class CalendarPostgresTests(unittest.TestCase):
    def setUp(self):
        self.url=os.environ["CORA_CALENDAR_TEST_DATABASE_URL"]
        @contextmanager
        def connection():
            with psycopg.connect(self.url,row_factory=dict_row,prepare_threshold=None) as conn:
                yield conn
        self.patch=patch.object(store,"db_connection",connection); self.patch.start()
        with connection() as conn:
            schema=Path("database/schema.sql").read_text()
            conn.execute(schema[schema.index("CREATE TABLE IF NOT EXISTS calendar_events"):])
            conn.execute("TRUNCATE calendar_proposals,calendar_event_history,calendar_events")
        app=FastAPI(); app.include_router(router)
        self.env=patch.dict(os.environ,{"CORA_CALENDAR_TOKEN":"owner"}); self.env.start()
        self.client=TestClient(app,headers={"Authorization":"Bearer owner"})
        self.base="/api/v1/calendar"

    def tearDown(self):
        self.client.close(); self.env.stop(); self.patch.stop()

    def create(self, **delta):
        response=self.client.post(self.base+"/events",json={**DATA,**delta})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def list(self, deleted=False):
        return self.client.get(self.base+"/events",params={"start":"2026-10-02T00:00:00+02:00","end":"2026-10-03T00:00:00+02:00","deleted":deleted}).json()

    def test_persistence_updates_conflicts_soft_delete_restore_and_audit(self):
        event=self.create(); eid=event["id"]
        self.assertEqual(self.list()[0]["id"],eid)
        updated=self.client.patch(self.base+"/events/"+eid,json={**DATA,"title":"Aggiornato","version":1})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()["version"],2)
        self.assertEqual(self.client.delete(self.base+"/events/"+eid+"?version=1").status_code,409)
        removed=self.client.delete(self.base+"/events/"+eid+"?version=2")
        self.assertEqual(removed.status_code,200,removed.text)
        self.assertEqual(self.list(),[]); self.assertEqual(len(self.list(True)),1)
        self.assertEqual(self.client.get(self.base+"/events/"+eid).status_code,404)
        restored=self.client.post(self.base+"/events/"+eid+"/restore?version=3")
        self.assertEqual(restored.status_code,200,restored.text)
        self.assertEqual(restored.json()["version"],4)
        history=self.client.get(self.base+"/events/"+eid+"/history").json()
        self.assertEqual([h["action"] for h in history],["restore","delete","update","create"])

    def test_interval_includes_cross_midnight_but_excludes_touching_boundaries(self):
        self.create(start="2026-10-01T23:30:00+02:00",end="2026-10-02T00:30:00+02:00")
        self.create(title="Ends at boundary",start="2026-10-01T22:00:00+02:00",end="2026-10-02T00:00:00+02:00")
        self.create(title="Starts at boundary",start="2026-10-03T00:00:00+02:00",end="2026-10-03T01:00:00+02:00")
        self.assertEqual(len(self.list()),1)

    def test_agent_proposal_cannot_write_before_approval_or_replay(self):
        pending=store.propose_event("email_quotes_agent","create",data=DATA,reason="Richiesta utente")
        self.assertEqual(self.list(),[])
        pid=pending["proposal"]["id"]
        self.assertEqual(len(self.client.get(self.base+"/proposals").json()),1)
        approved=self.client.post(self.base+"/proposals/"+pid+"/resolve",json={"approve":True})
        self.assertEqual(approved.status_code,200,approved.text)
        self.assertEqual(self.list()[0]["created_by"],"email_quotes_agent")
        self.assertEqual(self.client.post(self.base+"/proposals/"+pid+"/resolve",json={"approve":True}).status_code,409)
        self.assertEqual(len(self.list()),1)

    def test_proposal_conflict_does_not_apply_or_resolve_then_can_reject(self):
        event=self.create()
        pending=store.propose_event("supervisor","delete",event_id=event["id"],version=1)
        self.assertEqual(pending["proposal"]["previous"]["title"],"Cliente")
        store.write_event("update",event_id=event["id"],version=1,data={**DATA,"title":"Nuovo"})
        pid=pending["proposal"]["id"]
        self.assertEqual(self.client.post(self.base+"/proposals/"+pid+"/resolve",json={"approve":True}).status_code,409)
        self.assertEqual(self.list()[0]["title"],"Nuovo")
        self.assertEqual(len(store.list_proposals()),1)
        store.resolve_proposal(pid,False)
        self.assertEqual(store.list_proposals(),[])
        self.assertEqual(len(self.list()),1)

    def test_audit_failure_rolls_back_event(self):
        with patch.object(store,"_audit",side_effect=RuntimeError("test audit failure")):
            self.assertEqual(self.client.post(self.base+"/events",json=DATA).status_code,503)
        self.assertEqual(self.list(),[])

    def test_unknown_actor_is_blocked_before_creating_proposal(self):
        with self.assertRaises(PermissionError):
            store.propose_event("unknown","create",data=DATA)
        self.assertEqual(store.list_proposals(),[])

if __name__ == "__main__":
    unittest.main()
