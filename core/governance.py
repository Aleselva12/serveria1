"""Actor-bound tool execution, approvals and executable capability registry."""
import contextvars
import functools
import inspect
import hashlib
import ast
import importlib
import textwrap
import json
import time
from datetime import datetime, timezone
from uuid import uuid4, UUID
from langchain_core.tools import tool as langchain_tool
from psycopg.types.json import Jsonb
from core.database import db_connection
from core.runtime import current_run, checkpoint
from core.event_bus import bus

invocation = contextvars.ContextVar("tool_invocation", default=None)
approved_action = contextvars.ContextVar("approved_action", default=None)
executables = {}

class ApprovalRequired(BaseException):
    def __init__(self, actor, action):
        self.actor, self.action = actor, action


def agent_tool(actor):
    def decorate(fn):
        identifier = fn.__module__ + ":" + fn.__name__ + ":" + actor
        @functools.wraps(fn)
        def guarded(*args, **kwargs):
            checkpoint()
            payload = dict(inspect.signature(fn).bind(*args, **kwargs).arguments)
            token = invocation.set({"actor": actor, "tool_id": identifier, "payload": payload})
            started = time.perf_counter()
            run = current_run.get()
            try:
                from core.permissions import require_permission, get_permission_rule
                if fn.__name__ not in {"calendar_create_event", "calendar_update_event", "calendar_delete_event"}:
                    for action in sorted(actions):
                        rule = get_permission_rule(actor, action)
                        # Conditional BLOCKED branches are checked by the function.
                        if rule and rule.policy.value != "blocked": require_permission(actor, action)
                return fn(*args, **kwargs)
            except ApprovalRequired as needed:
                from core.permissions import get_permission_rule
                required = sorted({needed.action} | {a for a in actions if get_permission_rule(actor,a) and get_permission_rule(actor,a).policy.value == "confirm"})
                row = propose(needed.actor, needed.action, identifier, payload, actions=required)
                if run: run.approvals.append(str(row["id"]))
                return json.dumps({"status": "pending", "approval_id": str(row["id"]),
                    "message": "Azione non eseguita. Richiede conferma nella pagina Attività."})
            finally:
                invocation.reset(token)
                bus.publish("tool.finished", actor, run_id=run.id if run else None,
                    payload={"tool_id": identifier, "duration_ms": round((time.perf_counter()-started)*1000,2)})
        wrapped = langchain_tool(guarded)
        actions = set()
        source = inspect.getsource(fn)
        revision = hashlib.sha256(source.encode()).hexdigest()
        try:
            tree = ast.parse(textwrap.dedent(source))
            for call in ast.walk(tree):
                if isinstance(call, ast.Call):
                    action_map = {"create_plan_record":"create_plan", "save_plan_record":"save_plan", "create_evaluation_record":"create_evaluation", "save_evaluation_record":"save_evaluation", "create_management_record":"create_management", "save_management_record":"save_management", "list_artifacts":"read_structure_workspace", "read_artifact":"read_structure_workspace"}
                    mapped = action_map.get(ast.unparse(call.func))
                    if mapped: actions.add(mapped)
                if isinstance(call, ast.Call) and "permission" in ast.unparse(call.func):
                    actions.update(a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value != actor)
        except (OSError, TypeError, SyntaxError): pass
        if fn.__name__.startswith("calendar_"):
            action = fn.__name__.replace("calendar_", "").replace("_events", "_event")
            actions.add("calendar_" + action)
        executables[identifier] = {"actor": actor, "tool": wrapped, "actions": sorted(actions), "revision": revision}
        return wrapped
    return decorate


def propose(actor, action, tool_id, payload, actions=None):
    with db_connection() as conn:
        row = conn.execute("""INSERT INTO action_approvals (id,actor,action,tool_id,payload,actions,tool_revision)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""", (uuid4(),actor,action,tool_id,Jsonb(payload),Jsonb(actions or [action]),executables[tool_id]["revision"])).fetchone()
    return row


def list_approvals():
    with db_connection() as conn:
        return conn.execute("SELECT * FROM action_approvals WHERE status='pending' AND expires_at>NOW() ORDER BY created_at").fetchall()


def resolve(identifier, approve, username):
    # Claim once in a committed transaction before executing an external effect.
    # A crash after claim leaves 'executing', never silently replays the action.
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM action_approvals WHERE id=%s FOR UPDATE", (UUID(identifier),)).fetchone()
        if not row: raise KeyError(identifier)
        if row["status"] != "pending": raise ValueError("Richiesta già gestita.")
        if row["expires_at"] <= datetime.now(timezone.utc): raise ValueError("Richiesta scaduta.")
        conn.execute("UPDATE action_approvals SET status=%s,resolved_at=NOW(),resolved_by=%s WHERE id=%s",
            ("executing" if approve else "rejected",username,row["id"]))
    if not approve: return {"status": "rejected"}
    entry = executables.get(row["tool_id"])
    token = approved_action.set((row["actor"], frozenset(row["actions"] or [row["action"]]), row["tool_id"], row["payload"]))
    try:
        if not entry or entry["actor"] != row["actor"] or entry["revision"] != row["tool_revision"]: raise PermissionError("Capability non disponibile.")
        result = entry["tool"].invoke(row["payload"])
        parsed = result
        if isinstance(result, str):
            try: parsed = json.loads(result)
            except ValueError: pass
        status, error = ("failed", "ToolReportedError") if isinstance(parsed, dict) and parsed.get("status") in {"error", "pending"} else ("approved", None)
    except Exception as exc:
        status, error, result = "failed", type(exc).__name__, None
    finally:
        approved_action.reset(token)
    with db_connection() as conn:
        conn.execute("UPDATE action_approvals SET status=%s,error_type=%s,result=%s WHERE id=%s", (status,error,Jsonb(result),row["id"]))
    if status == "failed": raise RuntimeError(error)
    return {"status": status, "result": result, "error_type": error}


def capability_registry():
    from core.permissions import permission_manifest
    from core.registry import get_registry
    from core.tool_inventory import SOURCES
    for source, *_ in SOURCES:
        importlib.import_module(source[:-3].replace("/", "."))
    manifest = permission_manifest()
    declared = {(p["actor"],p["action"]):p for p in manifest}
    missing = [{"tool_id": key, "actor": val["actor"], "action": action}
        for key,val in executables.items() for action in val["actions"] if (val["actor"],action) not in declared]
    return {"version": 1, "validation": {"valid": not missing, "missing_permissions": missing}, "components": get_registry()["components"], "permissions": manifest,
        "tools": [{"id": key, "actor": val["actor"], "name": val["tool"].name,
            "actions": val["actions"], "revision": val["revision"], "permissions": [declared[(val["actor"],action)] for action in val["actions"] if (val["actor"],action) in declared], "input_schema": val["tool"].args} for key,val in sorted(executables.items())]}


def approval_history():
    with db_connection() as conn:
        return conn.execute("SELECT * FROM action_approvals WHERE status!='pending' OR expires_at<=NOW() ORDER BY created_at DESC LIMIT 50").fetchall()
