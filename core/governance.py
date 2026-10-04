"""Actor-bound tool execution, approvals and executable capability registry."""
import contextvars
import functools
import inspect
import hashlib
import importlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid4, UUID
from pathlib import Path
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


def agent_tool(actor, *, capability=None, actions, effect, retry, conditional_actions=(), version=1, approval="generic", response_mode="data"):
    """Register an explicit contract; the LangChain tool is only an adapter."""
    def decorate(fn):
        from pydantic import ConfigDict, TypeAdapter, create_model
        from typing import get_type_hints, Any
        from core.capability_contracts import CapabilityContract, CapabilityResult
        identifier = fn.__module__ + ":" + fn.__name__ + ":" + actor
        capability_id = actor + "." + (capability or fn.__name__)
        @functools.wraps(fn)
        def guarded(*args, **kwargs):
            payload = dict(inspect.signature(fn).bind(*args, **kwargs).arguments)
            result = execute_capability(capability_id, payload)
            if result.status == "error":
                if result.error.code in {"EffectUncertain", "OperationConflict"}:
                    from core.run_states import EffectUncertain
                    raise EffectUncertain(result.error.message)
                raise CapabilityExecutionError(result.error.code, result.error.message)
            return result.native
        wrapped = langchain_tool(guarded)
        schema = create_model(fn.__name__ + "Input", __base__=wrapped.args_schema,
                              __config__=ConfigDict(extra="forbid", strict=True))
        wrapped.args_schema = schema
        output = TypeAdapter(get_type_hints(fn).get("return", Any))
        contract = CapabilityContract(id=capability_id, version=version, actor=actor, name=fn.__name__,
            description=inspect.getdoc(fn) or "", required_actions=tuple(actions), conditional_actions=tuple(conditional_actions),
            effect=effect, retry=retry, approval=approval, response_mode=response_mode, input_schema=schema.model_json_schema(),
            native_output_schema=output.json_schema(), output_schema=CapabilityResult.model_json_schema())
        if not actions and not conditional_actions: raise ValueError("Declare at least one permission action")
        if set(actions) & set(conditional_actions): raise ValueError("Required and conditional actions overlap")
        if retry == "safe" and effect in {"write", "delegate"}: raise ValueError("Writes and delegations are not safely repeatable")
        digest = hashlib.sha256(contract.model_dump_json().encode()).hexdigest()
        # Changing an implementation invalidates exact-action approvals, even when input stayed compatible.
        module_file = inspect.getsourcefile(fn)
        implementation = Path(module_file).read_bytes() if module_file else fn.__code__.co_code
        revision = hashlib.sha256(implementation + Path(__file__).read_bytes() + digest.encode()).hexdigest()
        collision = next((e for key,e in executables.items() if e["contract"].id == capability_id and key != identifier), None)
        if collision: raise ValueError("Duplicate capability identity: " + capability_id)
        existing = executables.get(identifier)
        if existing and existing["contract_digest"] != digest: raise ValueError("Conflicting capability contract: " + capability_id)
        executables[identifier] = {"actor":actor,"tool":wrapped,"fn":fn,"input_model":schema,"output_adapter":output,
            "contract":contract,"contract_digest":digest,"actions":sorted(set(actions)|set(conditional_actions)),
            "revision":revision,"connected":bool(existing and existing.get("connected"))}
        return wrapped
    return decorate


class CapabilityExecutionError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def find_capability(identifier):
    entry = executables.get(identifier)
    if entry: return identifier, entry
    matches = [(key,e) for key,e in executables.items() if e["contract"].id == identifier]
    if not matches: raise KeyError(identifier)
    return matches[0]


def tool_contract(tool):
    entry = next((e for e in executables.values() if e["tool"] is tool),None)
    if not entry: raise KeyError(tool.name)
    return entry["contract"]


def bind_capabilities(actor, tools):
    """Register the exact tools assigned to a graph; no AST guesses about connections."""
    for tool in tools:
        entry = next((e for e in executables.values() if e["tool"] is tool), None)
        if not entry or entry["actor"] != actor: raise ValueError("Unregistered tool or actor mismatch: " + tool.name)
        entry["connected"] = True
    return tools


def execute_capability(identifier, payload):
    from core.capability_contracts import CapabilityResult, CapabilityError
    from fastapi.encoders import jsonable_encoder
    tool_id, entry = find_capability(identifier)
    contract = entry["contract"]
    result = CapabilityResult(capability_id=contract.id, contract_version=contract.version, status="ok")
    token = None
    operation_id = None
    escaped_error = None
    started = time.perf_counter()
    run = current_run.get()
    try:
        checkpoint()
        payload = entry["input_model"].model_validate(payload).model_dump()
        token = invocation.set({"actor":contract.actor,"tool_id":tool_id,"payload":payload,"actions":entry["actions"]})
        from core.permissions import require_permission, get_permission_rule
        for action in contract.required_actions:
            rule = get_permission_rule(contract.actor, action)
            if not rule or rule.policy.value == "blocked": require_permission(contract.actor, action)
        for action in contract.required_actions:
            rule = get_permission_rule(contract.actor, action)
            if contract.approval == "calendar" and rule and rule.policy.value == "confirm": continue
            require_permission(contract.actor, action)
        from core.operation_journal import begin
        operation_id = begin(entry, payload)
        result.operation_id = operation_id
        native = entry["fn"](**payload)
        native = entry["output_adapter"].validate_python(native, strict=True)
        parsed = native
        if isinstance(native, str):
            try: parsed = json.loads(native)
            except ValueError: pass
        if isinstance(parsed, dict) and (parsed.get("status") in {"error","failed"} or ("error" in parsed and parsed["error"])):
            result.status = "error"
            result.error = CapabilityError(code="ToolReportedError", message=str(parsed.get("error") or "Operazione non completata."))
        elif isinstance(parsed, dict) and parsed.get("status") == "pending":
            result.status = "pending"
            proposal = parsed.get('proposal')
            identity = parsed.get("approval_id") or parsed.get("proposal_id") or parsed.get("id") or (proposal.get('id') if isinstance(proposal,dict) else None)
            result.approval_id = str(identity) if identity else None
            if result.approval_id and contract.approval == 'calendar' and not result.approval_id.startswith('calendar:'):
                result.approval_id = 'calendar:' + result.approval_id
        result.value = jsonable_encoder(parsed)
        result.native = native
    except ApprovalRequired as needed:
        try:
            from core.permissions import get_permission_rule
            required = sorted({needed.action} | {a for a in contract.required_actions if get_permission_rule(contract.actor,a).policy.value == "confirm"})
            row = propose(needed.actor, needed.action, tool_id, payload, actions=required)
            if run: run.approvals.append(str(row["id"]))
            result.status, result.approval_id = "pending", str(row["id"])
            result.native = json.dumps({"status":"pending","approval_id":result.approval_id,"message":"Azione non eseguita. Richiede conferma nella pagina Attività."})
        except Exception as error:
            result.status = "error"
            result.error = CapabilityError(code=type(error).__name__, message="Impossibile creare la richiesta di conferma.")
    except Exception as error:
        result.status = "error"
        result.error = CapabilityError(code=type(error).__name__, message="Operazione non completata: " + type(error).__name__ + ".")
    except BaseException as error:
        escaped_error = type(error).__name__
        result.status = "error"
        raise
    finally:
        if token: invocation.reset(token)
        # Validate before publishing so technical events reflect the canonical outcome.
        # Cancellation is a BaseException and escapes without a normal result.
        if result.status != "error" or result.error is not None:
            try:
                wire = CapabilityResult.model_validate(result.model_dump())
                wire.native = result.native
                result = wire
            except Exception as error:
                result = CapabilityResult(capability_id=contract.id, contract_version=contract.version,
                    status="error", operation_id=operation_id, error=CapabilityError(code=type(error).__name__, message="Risultato non conforme al contratto."))
        if run and result.status == 'pending' and result.approval_id:
            with run.lock:
                if result.approval_id not in run.approvals: run.approvals.append(result.approval_id)
        from core.operation_journal import finish
        operation_status = finish(operation_id, contract.effect, None if escaped_error else result, escaped_error)
        if operation_status == 'uncertain' and not escaped_error:
            result.error = CapabilityError(code='EffectUncertain',message='Esito dell’effetto non verificabile. Controlla l’operazione in Attività prima di ripetere.')
        bus.publish("tool.finished", contract.actor, run_id=run.id if run else None,
            operation_id=operation_id,payload={"tool_id":tool_id,"capability_id":contract.id,"contract_version":contract.version,
            "status":result.status,"operation_id":operation_id,'error_type':escaped_error or (result.error.code if result.error else None),"duration_ms":round((time.perf_counter()-started)*1000,2)})
    return result


def propose(actor, action, tool_id, payload, actions=None):
    with db_connection() as conn:
        row = conn.execute("""INSERT INTO action_approvals (id,actor,action,tool_id,payload,actions,tool_revision)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""", (uuid4(),actor,action,tool_id,Jsonb(payload),Jsonb(actions or [action]),executables[tool_id]["revision"])).fetchone()
        entry = executables[tool_id]
        conn.execute("UPDATE action_approvals SET capability_id=%s,contract_version=%s,contract_digest=%s WHERE id=%s",
            (entry["contract"].id,entry["contract"].version,entry["contract_digest"],row["id"]))
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
    token = None
    approval_token = None
    escaped = None
    from core.run_states import DurabilityLost, EffectUncertain
    from core.runtime import RunStopped
    try:
        load_capabilities()
        entry = executables.get(row["tool_id"])
        if not entry or entry["actor"] != row["actor"] or entry["revision"] != row["tool_revision"]: raise PermissionError("Capability non disponibile.")
        if (row["capability_id"],row["contract_version"],row["contract_digest"]) != (entry["contract"].id,entry["contract"].version,entry["contract_digest"]): raise PermissionError("Contratto della proposta non disponibile. Crea una nuova proposta.")
        normalized = entry["input_model"].model_validate(row["payload"]).model_dump()
        token = approved_action.set((row["actor"],frozenset(row["actions"] or [row["action"]]),row["tool_id"],normalized))
        from core.operation_journal import current_approval
        approval_token = current_approval.set(row['id'])
        outcome = execute_capability(entry["contract"].id,normalized)
        result = outcome.native if outcome.status != "error" else outcome.model_dump(mode="json")
        parsed = result
        if isinstance(result, str):
            try: parsed = json.loads(result)
            except ValueError: pass
        status, error = ("failed", "ToolReportedError") if isinstance(parsed, dict) and parsed.get("status") in {"error", "pending"} else ("approved", None)
        if outcome.error and outcome.error.code in {'EffectUncertain','OperationConflict'}:
            status, error = 'uncertain', 'EffectUncertain'
    except DurabilityLost:
        raise
    except (RunStopped, EffectUncertain) as exc:
        escaped = exc
        status, error, result = 'uncertain', type(exc).__name__, None
    except Exception as exc:
        status, error, result = "failed", type(exc).__name__, None
    finally:
        if token: approved_action.reset(token)
        if approval_token is not None: current_approval.reset(approval_token)
    try:
        with db_connection() as conn:
            conn.execute("UPDATE action_approvals SET status=%s,error_type=%s,result=%s WHERE id=%s", (status,error,Jsonb(result),row["id"]))
    except Exception as persistence_error:
        raise DurabilityLost('ApprovalOutcomeNotPersisted') from persistence_error
    if escaped: raise escaped
    if status in {"failed", "uncertain"}: raise RuntimeError(error)
    return {"status": status, "result": result, "error_type": error}


def load_capabilities():
    from core.tool_inventory import SOURCES
    for source, graph, *_ in SOURCES:
        importlib.import_module(source[:-3].replace("/", "."))
        importlib.import_module(graph[:-3].replace("/", "."))


def capability_manifest(entry):
    from core.permissions import get_permission_rule
    contract = entry["contract"]
    rules = [get_permission_rule(contract.actor,a) for a in entry["actions"]]
    return {**contract.model_dump(mode="json"), "tool_id":entry["fn"].__module__+":"+entry["fn"].__name__+":"+contract.actor,
        "contract_digest":entry["contract_digest"],"implementation_revision":entry["revision"],
        "connected":entry["connected"],"permissions":[r.to_dict() for r in rules if r]}


def capability_registry():
    from core.permissions import permission_manifest
    from core.registry import get_registry
    load_capabilities()
    manifest = permission_manifest()
    declared = {(p["actor"],p["action"]):p for p in manifest}
    missing = [{"tool_id":key,"actor":val["actor"],"action":action}
        for key,val in executables.items() for action in val["actions"] if (val["actor"],action) not in declared]
    return {"version":2,"validation":{"valid":not missing,"missing_permissions":missing},
        "components":get_registry()["components"],"permissions":manifest,
        "tools":[{**capability_manifest(val),"actions":val["actions"],"revision":val["revision"]} for key,val in sorted(executables.items())]}


def approval_history():
    with db_connection() as conn:
        return conn.execute("SELECT * FROM action_approvals WHERE status!='pending' OR expires_at<=NOW() ORDER BY created_at DESC LIMIT 50").fetchall()
