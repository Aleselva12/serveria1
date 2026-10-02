"""Compatibility facade; governed bound tool requests are the only executable approvals."""
from core.governance import list_approvals as _list, propose, resolve, executables
from core.permissions import get_permission_rule

class ApprovalConflict(RuntimeError):
    pass


def request_approval(*, actor, action, payload=None, reason="", metadata=None, ttl_minutes=60):
    identifier = (metadata or {}).get("tool_id")
    entry = executables.get(identifier)
    rule = get_permission_rule(actor,action)
    if not rule or rule.policy.value != "confirm" or not entry or entry["actor"] != actor or action not in entry["actions"]:
        raise PermissionError("Serve una capability eseguibile con parametri esatti e policy confirm.")
    return propose(actor,action,identifier,payload or {})


def list_approvals(status="pending",limit=100):
    if status != "pending":
        from core.governance import approval_history
        return approval_history()[:limit]
    return _list()[:limit]


def resolve_approval(approval_id,approve,*,resolved_by="owner"):
    try: return resolve(approval_id,approve,resolved_by)
    except ValueError as error: raise ApprovalConflict(str(error)) from error


def consume_approval(*args,**kwargs):
    raise ApprovalConflict("Non esistono grant riutilizzabili: risolvi la proposta per eseguire il tool con i suoi parametri esatti.")
