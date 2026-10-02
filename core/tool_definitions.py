"""Static, condensed diagrams and signatures. Never invokes the selected tool."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from core.tool_inventory import ROOT, _parse, _tool_functions, inventory

CALL_LABELS = {
    "store.propose_event": "Prepara una proposta calendario",
    "store.list_events": "Legge gli eventi dal calendario",
    "store.get_event": "Legge l’evento e la sua versione",
    "search_messages": "Cerca nell’archivio Gmail",
    "get_message": "Legge il messaggio Gmail",
    "messages_for_day": "Recupera le email del giorno",
    "save_as_draft": "Salva una bozza Gmail",
    "save_memory": "Salva la memoria",
    "search_memories": "Cerca nelle memorie",
    "delete_memory": "Elimina la memoria selezionata",
    "save_plan_record": "Salva il piano",
    "save_evaluation_record": "Salva la valutazione",
    "save_management_record": "Salva il documento di gestione",
}


def _signature(fn):
    args = fn.args.posonlyargs + fn.args.args
    defaults = [None] * (len(args) - len(fn.args.defaults)) + list(fn.args.defaults)
    args += fn.args.kwonlyargs
    defaults += list(fn.args.kw_defaults)
    return [dict(name=a.arg, type=ast.unparse(a.annotation) if a.annotation else "Non dichiarato",
                 required=d is None, default=ast.unparse(d) if d is not None else None)
            for a, d in zip(args, defaults)]


def _flow(entry, fn):
    # Summarise categories of steps rather than pretending AST order is a runtime trace.
    calls = list(dict.fromkeys(ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)))
    permission = [c for c in calls if "permission" in c]
    conditions = list(dict.fromkeys(ast.unparse(n.test) for n in ast.walk(fn) if isinstance(n, ast.If)))
    operations = [c for c in calls if c not in permission and not c.startswith("json.") and
                  c not in {"dict", "list", "str", "int", "float", "len", "max", "min", "bool", "print", "range", "enumerate", "isinstance", "ValueError", "PermissionError"}]
    approval = "store.propose_event" in calls
    nodes, edges = [], []

    def add(kind, label, detail, x, y=160):
        ident = f"step-{len(nodes)}"
        nodes.append(dict(id=ident, kind=kind, label=label, detail=detail, x=x, y=y, config={}))
        return ident

    current = add("trigger", "Ingresso", ", ".join(a["name"] for a in _signature(fn)) or "Nessun parametro", 50)
    if permission or conditions:
        ident = add("condition", "Permessi e controlli", "\n".join(permission + conditions), 330)
        edges.append(dict(id=f"edge-{len(edges)}", source=current, target=ident, label="parametri"))
        current = ident
    action_x = 610 if permission or conditions else 330
    primary = next((CALL_LABELS[c] for c in operations if c in CALL_LABELS), entry["name"])
    action = add("tool", primary, entry["description"], action_x)
    edges.append(dict(id=f"edge-{len(edges)}", source=current, target=action, label="elaborazione"))
    output = add("output", "Proposta da approvare" if approval else "Risultato", "L’evento cambia solo dopo l’approvazione dell’utente." if approval else
                 "Tipo dichiarato: " + (ast.unparse(fn.returns) if fn.returns else "Non dichiarato"), action_x + 280)
    edges.append(dict(id=f"edge-{len(edges)}", source=action, target=output, label="proposta" if approval else "output"))
    if any(isinstance(n, ast.ExceptHandler) for n in ast.walk(fn)):
        err = add("output", "Gestione degli errori", "Il codice contiene una gestione esplicita delle eccezioni; il risultato può segnalare un errore.", action_x, 360)
        edges.append(dict(id=f"edge-{len(edges)}", source=action, target=err, label="errore", dashed=True))
    return dict(nodes=nodes, edges=edges), operations, permission, conditions


def definition(tool_id, routes=(), root: Path = ROOT):
    from core.tool_inventory import flatten_routes
    routes = list(flatten_routes(routes))
    entry = next((e for e in inventory(routes, root)["entries"] if e["id"] == tool_id), None)
    if entry is None:
        raise KeyError("Strumento non presente nell’inventario.")
    fn = None
    if entry["kind"] == "tool":
        fn = next((f for f in _tool_functions(_parse(root / entry["source"])) if f.name == entry["name"]), None)
    elif entry["kind"] == "api":
        _, method, path = tool_id.split(":", 2)
        route = next((r for r in routes if getattr(r, "path", "") == path and method in (getattr(r, "methods", ()) or ())), None)
        if route and getattr(route, "endpoint", None):
            try:
                import textwrap
                parsed = ast.parse(textwrap.dedent(inspect.getsource(route.endpoint)))
                fn = next((n for n in parsed.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
            except (OSError, TypeError, SyntaxError):
                pass
    if fn is None:
        return dict(entry=entry, parameters=[], output_type="Non dichiarato", operations=[], checks=[], conditions=[],
                    flow=dict(nodes=[dict(id="step-0", kind="tool", label=entry["name"], detail=entry["description"], x=100, y=160, config={})], edges=[]),
                    note="Predisposizione senza implementazione." if entry["kind"] == "planned" else "Dettagli del codice non disponibili per questa operazione.")
    flow, operations, checks, conditions = _flow(entry, fn)
    return dict(entry=entry, parameters=_signature(fn), output_type=ast.unparse(fn.returns) if fn.returns else "Non dichiarato",
                operations=operations, checks=checks, conditions=conditions, flow=flow,
                note="Schema sintetico letto dal codice: raggruppa controlli, operazione e risultato. I rami interni e i cicli non sono rappresentati integralmente; non è una traccia di esecuzione.")
