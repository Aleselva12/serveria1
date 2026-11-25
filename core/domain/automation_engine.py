"""Pure execution logic for automation drafts: references, conditions and graph stepping.

No I/O happens here. Tools are called through the ``execute`` callable the caller
injects (in production ``core.governance.execute_capability``), so the same permission,
approval and operation-journal rules apply as when an agent calls the tool.

A run record holds one entry per node. ``advance`` settles nodes in dependency order
until the run finishes, fails, or a tool waits for the owner's approval; calling it
again after the approval resumes from the same point.
"""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime

REF = re.compile(r"\{\{\s*([A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*)\s*\}\}")
OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "not_contains", "empty", "not_empty"}
UNARY = {"empty", "not_empty"}
SETTLED = {"done", "skipped", "simulated"}
WRITE_EFFECTS = {"write", "delegate"}
YES, NO = "sì", "no"


class RunFailure(Exception):
    """A node cannot run; the message is shown to the owner."""


class Simulated:
    """Placeholder for a value a dry run did not produce."""

    def __init__(self, ref):
        self.ref = ref

    def __repr__(self):
        return f"«simulato: {self.ref}»"


def now():
    return datetime.now(UTC).isoformat()


def _contains_simulated(value):
    if isinstance(value, Simulated):
        return True
    if isinstance(value, dict):
        return any(_contains_simulated(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_simulated(v) for v in value)
    return False


def _plain(value):
    """JSON-safe copy for the run record, with placeholders spelled out."""
    if isinstance(value, Simulated):
        return repr(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def references(value):
    """Every ``{{root.path}}`` reference inside a node configuration."""
    found = []
    if isinstance(value, str):
        found.extend(m.group(1) for m in REF.finditer(value))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(references(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(references(item))
    return found


def _lookup(ref, run, labels):
    root, *path = ref.split(".")
    if root == "input":
        current = run.get("input") or {}
    else:
        state = run["nodes"].get(root)
        if state is None:
            raise RunFailure(f"Riferimento «{ref}»: passaggio inesistente.")
        if state["status"] == "simulated":
            return Simulated(ref)
        if state["status"] != "done":
            raise RunFailure(f"Riferimento «{ref}»: il passaggio «{labels.get(root, root)}» non è stato eseguito.")
        current = state.get("result")
    for step in path:
        if isinstance(current, dict) and step in current:
            current = current[step]
        elif isinstance(current, list) and step.isdigit() and int(step) < len(current):
            current = current[int(step)]
        else:
            where = "nei valori di avvio" if root == "input" else f"nel risultato di «{labels.get(root, root)}»"
            raise RunFailure(f"Riferimento «{ref}»: «{step}» non trovato {where}.")
    return current


def resolve(value, run, labels):
    """Replace references. A string that is only a reference keeps the referenced type."""
    if isinstance(value, str):
        whole = REF.fullmatch(value.strip())
        if whole:
            return _lookup(whole.group(1), run, labels)

        def text(match):
            found = _lookup(match.group(1), run, labels)
            if isinstance(found, Simulated):
                return repr(found)
            return found if isinstance(found, str) else json.dumps(found, ensure_ascii=False)

        replaced = REF.sub(text, value)
        # Keep the placeholder visible so the node is reported as simulated.
        return Simulated(value) if "«simulato:" in replaced and "«simulato:" not in value else replaced
    if isinstance(value, dict):
        return {k: resolve(v, run, labels) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, run, labels) for v in value]
    return value


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def evaluate(rule, left, right):
    op = rule.get("op")
    if op == "empty":
        return left in (None, "", [], {}) or (isinstance(left, (list, dict, str)) and len(left) == 0)
    if op == "not_empty":
        return not evaluate({"op": "empty"}, left, None)
    if op in {"contains", "not_contains"}:
        if isinstance(left, (list, tuple)):
            found = right in left or str(right) in [str(item) for item in left]
        elif isinstance(left, dict):
            found = str(right) in left
        else:
            found = str(right).casefold() in str(left if left is not None else "").casefold()
        return found if op == "contains" else not found
    if op in {"eq", "ne"}:
        if isinstance(left, (dict, list)) or isinstance(right, (dict, list)):
            same = left == right
        else:
            a, b = _number(left), _number(right)
            same = a == b if a is not None and b is not None else str(left).strip() == str(right).strip()
        return same if op == "eq" else not same
    a, b = _number(left), _number(right)
    if a is None or b is None:
        raise RunFailure(f"Confronto «{op}» possibile solo fra numeri: ricevuti {json.dumps(_plain(left), ensure_ascii=False)} e {json.dumps(_plain(right), ensure_ascii=False)}.")
    return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]


def check_rule(rule):
    if not isinstance(rule, dict) or rule.get("op") not in OPERATORS or "left" not in rule:
        return "regola incompleta: servono «left», «op» e, se richiesto, «right»."
    if rule["op"] not in UNARY and "right" not in rule:
        return "manca il valore «right» da confrontare."
    return None


def predecessors(edges):
    incoming = {}
    for edge in edges:
        incoming.setdefault(edge["target"], []).append(edge)
    return incoming


def ancestors(node_id, edges):
    incoming, seen, stack = predecessors(edges), set(), [node_id]
    while stack:
        for edge in incoming.get(stack.pop(), []):
            if edge["source"] not in seen:
                seen.add(edge["source"])
                stack.append(edge["source"])
    return seen


def order(nodes, edges):
    """Topological order; the drafts store already rejects cycles."""
    incoming = {n["id"]: 0 for n in nodes}
    for edge in edges:
        incoming[edge["target"]] += 1
    position = {n["id"]: i for i, n in enumerate(nodes)}
    ready = sorted([i for i, c in incoming.items() if c == 0], key=position.get)
    result = []
    while ready:
        current = ready.pop(0)
        result.append(current)
        for edge in edges:
            if edge["source"] == current:
                incoming[edge["target"]] -= 1
                if incoming[edge["target"]] == 0:
                    ready.append(edge["target"])
                    ready.sort(key=position.get)
    return result


def preflight(graph, bindings):
    """Problems that make a run impossible. Returned as owner-facing sentences."""
    problems = []
    nodes = {n["id"]: n for n in graph["nodes"]}
    if not any(n["kind"] == "trigger" for n in graph["nodes"]):
        problems.append("Manca un ingresso: aggiungi un nodo di avvio.")
    for node in graph["nodes"]:
        label = node["label"]
        if node["kind"] == "tool":
            binding = bindings.get(node.get("tool_id") or "")
            if not node.get("tool_id"):
                problems.append(f"{label}: scegli un tool.")
            elif not binding:
                problems.append(f"{label}: il tool non ha un contratto eseguibile.")
            else:
                schema = binding.get("input_schema") or {}
                for name in schema.get("required") or []:
                    if name not in node.get("config", {}):
                        problems.append(f"{label}: manca il parametro obbligatorio «{name}».")
        if node["kind"] == "reminder":
            from core.domain.automation_schedule import TIME
            config = node["config"]
            if not isinstance(config.get("time"), str) or not TIME.fullmatch(config["time"]):
                problems.append(f"{label}: imposta un orario valido (HH:MM).")
        if node["kind"] == "condition":
            issue = check_rule(node.get("config"))
            if issue:
                problems.append(f"{label}: {issue}")
            labels = {e["label"] for e in graph["edges"] if e["source"] == node["id"]}
            if not {YES, NO} <= labels:
                problems.append(f"{label}: completa i rami sì e no.")
        allowed = ancestors(node["id"], graph["edges"])
        for ref in references(node.get("config", {})):
            root = ref.split(".")[0]
            if root == "input":
                continue
            if root not in nodes:
                problems.append(f"{label}: il riferimento «{ref}» punta a un passaggio inesistente.")
            elif root not in allowed:
                problems.append(f"{label}: il riferimento «{ref}» usa «{nodes[root]['label']}», che non lo precede nel flusso.")
    return problems


def input_names(graph):
    names = []
    for node in graph["nodes"]:
        for ref in references(node.get("config", {})):
            root, *path = ref.split(".")
            if root == "input" and path and path[0] not in names:
                names.append(path[0])
    return names


def new_run_nodes(graph):
    return {n["id"]: {"status": "pending", "kind": n["kind"], "label": n["label"]} for n in graph["nodes"]}


def _carries(edge, run):
    """A done source passes control along an edge, except a condition's unchosen branch."""
    source = run["nodes"][edge["source"]]
    return source["status"] == "done" and not (source["kind"] == "condition" and source.get("outcome") != edge["label"])


def _reach(node_id, run, incoming):
    """real: a real path leads here; simulated: only simulated paths; None: not reached."""
    reach = None
    for edge in incoming.get(node_id, []):
        if _carries(edge, run):
            return "real"
        if run["nodes"][edge["source"]]["status"] == "simulated":
            reach = "simulated"
    return reach


def _settle(state, status, started, **fields):
    state.update(status=status, finished_at=now(), duration_ms=round((time.perf_counter() - started) * 1000, 1), **fields)


def advance(run, graph, bindings, execute, *, should_stop=lambda: False, persist=lambda run: None):
    """Settle nodes until the run ends or waits. Mutates and returns ``run``."""
    labels = {n["id"]: n["label"] for n in graph["nodes"]}
    nodes = {n["id"]: n for n in graph["nodes"]}
    incoming = predecessors(graph["edges"])
    dry = run["mode"] == "dry_run"
    run["status"] = "running"
    for node_id in order(graph["nodes"], graph["edges"]):
        state = run["nodes"][node_id]
        if state["status"] in SETTLED:
            continue
        if state["status"] == "waiting_approval":
            run["status"] = "waiting_approval"
            return run
        if state["status"] in {"failed", "rejected"}:
            run["status"] = state["status"]
            run["error"] = f"{state['label']}: {state.get('error', 'operazione non completata.')}"
            return run
        if any(run["nodes"][e["source"]]["status"] not in SETTLED for e in incoming.get(node_id, [])):
            continue  # cannot happen in topological order, kept as a guard
        if should_stop():
            run["status"] = "cancelled"
            run["error"] = "Esecuzione annullata dall’utente."
            return run
        node = nodes[node_id]
        started = time.perf_counter()
        state.update(started_at=now())
        reach = "real" if node["kind"] == "trigger" else _reach(node_id, run, incoming)
        try:
            if reach is None:
                _settle(state, "skipped", started)
            elif node["kind"] == "trigger":
                _settle(state, "done", started, result=run.get("input") or {})
            elif node["kind"] == "output":
                values = {labels[e["source"]]: run["nodes"][e["source"]].get("result")
                          for e in incoming.get(node_id, []) if _carries(e, run)}
                _settle(state, "done" if reach == "real" else "simulated", started, result=values)
            elif node["kind"] == "reminder":
                _reminder(node, state, reach, run, dry, started)
            elif node["kind"] == "condition":
                _condition(node, state, reach, run, labels, started)
            else:
                _tool(node, state, reach, run, labels, bindings, execute, dry, started)
        except RunFailure as failure:
            _settle(state, "failed", started, error=str(failure))
            run.update(status="failed", error=f"{node['label']}: {failure}")
            return run
        persist(run)
        if state["status"] == "waiting_approval":
            run["status"] = "waiting_approval"
            return run
        if state["status"] in {"failed", "rejected"}:
            run["status"] = state["status"]
            run["error"] = f"{node['label']}: {state.get('error', 'operazione non completata.')}"
            return run
    run["status"] = "succeeded"
    return run


def _condition(node, state, reach, run, labels, started):
    rule = node.get("config") or {}
    issue = check_rule(rule)
    if issue:
        raise RunFailure(issue)
    if reach == "simulated":
        _settle(state, "simulated", started, outcome=None)
        return
    left = resolve(rule.get("left"), run, labels)
    right = None if rule["op"] in UNARY else resolve(rule.get("right"), run, labels)
    shown = {"left": _plain(left), "op": rule["op"], "right": _plain(right)}
    if _contains_simulated(left) or _contains_simulated(right):
        _settle(state, "simulated", started, input=shown, outcome=None)
        return
    outcome = YES if evaluate(rule, left, right) else NO
    _settle(state, "done", started, input=shown, outcome=outcome, result={"outcome": outcome})


def _reminder(node, state, reach, run, dry, started):
    from core.domain import automation_reminders, automation_schedule

    local_timezone = automation_schedule.timezone()
    current = datetime.now(local_timezone)
    run_day = datetime.fromisoformat(run["created_at"]).astimezone(local_timezone)
    hour, minute = map(int, node["config"]["time"].split(":"))
    delivery = run_day.replace(hour=hour, minute=minute, second=0, microsecond=0, fold=0)
    if delivery <= current:
        raise RunFailure("L’orario del promemoria per questo giorno è già passato.")
    result = {"deliver_at": delivery.isoformat()}
    if dry or reach == "simulated":
        _settle(state, "simulated", started, result=result)
        return
    result["notification_id"] = automation_reminders.schedule(run, node["id"], node["label"], delivery)
    _settle(state, "done", started, result=result)


def _tool(node, state, reach, run, labels, bindings, execute, dry, started):
    binding = bindings.get(node.get("tool_id") or "")
    if not binding:
        raise RunFailure("il tool non ha un contratto eseguibile.")
    payload = resolve(node.get("config") or {}, run, labels)
    state["input"] = _plain(payload)
    state["effect"] = binding["effect"]
    if reach == "simulated" or _contains_simulated(payload):
        _settle(state, "simulated", started, note="Dipende da un passaggio simulato: non eseguito.")
        return
    if dry and binding["effect"] in WRITE_EFFECTS:
        _settle(state, "simulated", started, note="Prova a vuoto: il tool modifica dati e non viene eseguito.")
        return
    outcome = execute(binding["capability"], payload)
    status = getattr(outcome, "status", None)
    if status == "ok":
        _settle(state, "done", started, result=_plain(getattr(outcome, "value", None)), operation_id=getattr(outcome, "operation_id", None))
    elif status == "pending":
        state.update(status="waiting_approval", approval_id=getattr(outcome, "approval_id", None),
                     operation_id=getattr(outcome, "operation_id", None))
        if not state["approval_id"]:
            raise RunFailure("il tool chiede una conferma ma non ha creato la richiesta.")
    else:
        error = getattr(outcome, "error", None)
        message = getattr(error, "message", None) or "operazione non completata."
        _settle(state, "failed", started, error=message, error_code=getattr(error, "code", None),
                operation_id=getattr(outcome, "operation_id", None))


def apply_approval(run, node_id, decision):
    """Record the owner's decision on a waiting node. ``decision`` comes from the approvals store."""
    state = run["nodes"][node_id]
    status = decision.get("status")
    if status == "approved":
        state.update(status="done", finished_at=now(), result=_plain(decision.get("result")))
    elif status == "rejected":
        state.update(status="rejected", finished_at=now(), error="richiesta rifiutata in Attività.")
    elif status == "expired":
        state.update(status="failed", finished_at=now(), error="richiesta di conferma scaduta.")
    else:
        state.update(status="failed", finished_at=now(),
                     error=f"esecuzione dopo la conferma non riuscita ({decision.get('error_type') or status}). Controlla in Attività prima di ripetere.")
    return state["status"]
