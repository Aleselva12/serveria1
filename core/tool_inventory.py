"""Read-only inventory of declared tools and registered HTTP operations.

No model, connector or tool is executed by this inspection.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ("tools.py", "graph.py", "supervisor_tools", "Cora / Supervisor", "Sistema e memoria"),
    ("structure_agent/structure_tools.py", "structure_agent/structure_graph.py", "STRUCTURE_TOOLS", "Structure Agent", "Struttura e pianificazione"),
    ("search_agent/search_tools.py", "search_agent/search_graph.py", "LOCAL_RESEARCH_TOOLS", "Local Research Agent", "Documenti"),
    ("audio_agent/audio_tools.py", "audio_agent/audio_graph.py", "AUDIO_TOOLS", "Audio Agent", "Audio"),
    ("email_agent/email_tools.py", "email_agent/email_graph.py", "EMAIL_TOOLS", "Email & Quotes Agent", "Email e preventivi"),
)


def _parse(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _tool_functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            isinstance(d, ast.Name) and d.id == "tool"
            or isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "tool"
            for d in node.decorator_list
        ):
            yield node


def _binding(tree, list_name, root=ROOT, seen=None):
    seen = set() if seen is None else seen
    if list_name in seen:
        return set()
    seen = seen | {list_name}
    names = set()
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == list_name for t in node.targets) or
            isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == list_name):
            # Include names in literal lists, concatenations and starred lists.
            for ref in (n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)):
                expanded = _binding(tree, ref, root, seen)
                if not expanded:
                    for imp in (n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module):
                        alias = next((a for a in imp.names if (a.asname or a.name) == ref), None)
                        imported_path = root / (imp.module.replace(".", "/") + ".py")
                        if alias and imported_path.is_file():
                            imported_tree = _parse(imported_path)
                            expanded = _binding(imported_tree, alias.name, root, seen)
                            factory = next((f for f in imported_tree.body if isinstance(f, ast.FunctionDef) and f.name == alias.name), None)
                            if factory and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == ref for n in ast.walk(node.value)):
                                declared = {f.name for f in _tool_functions(factory)}
                                expanded = {n.id for ret in ast.walk(factory) if isinstance(ret, ast.Return) for n in ast.walk(ret) if isinstance(n, ast.Name)} & declared
                            break
                names.update(expanded or {ref})
    return names


def _uses_list(tree, list_name):
    return any(isinstance(n, ast.Call) and
               (isinstance(n.func, ast.Name) and n.func.id == "ToolNode" or
                isinstance(n.func, ast.Attribute) and n.func.attr == "bind_tools") and
               any(isinstance(a, ast.Name) and a.id == list_name for a in n.args)
               for n in ast.walk(tree))


def inventory(routes=(), root: Path = ROOT):
    entries, errors = [], []
    for source, graph, list_name, owner, group in SOURCES:
        try:
            tree = _parse(root / source)
            bound = _binding(tree, list_name, root)
            attached = _uses_list(_parse(root / graph), list_name)
            for fn in _tool_functions(tree):
                connected = attached and fn.name in bound
                function_group = group
                if fn.name.startswith("calendar_"):
                    function_group = "Calendario"
                elif source == "tools.py":
                    function_group = ("Deleghe agli agenti" if fn.name.endswith("agent_tool") else
                                      "Memoria" if "memory" in fn.name or fn.name == "remember_tool" else "Sistema")
                entries.append(dict(id=f"{source}:{fn.name}", name=fn.name,
                    description=" ".join((ast.get_docstring(fn) or "Tool senza descrizione.").split()),
                    group=function_group, kind="tool", status="connected" if connected else "unconnected",
                    agents=[owner] if connected else [], source=source,
                    parameters=[a.arg for a in fn.args.args],
                    detail="Presente nel codice. Credenziali, modelli e permessi restano necessari per l’esecuzione."))
        except (OSError, SyntaxError) as error:
            errors.append(f"{source}: {type(error).__name__}")

    # Tool modules added by concurrent calendar work: discover declarations and
    # prove attachment through the actual graph imports/list references.
    known = {s[0] for s in SOURCES} | {"local_tools.py"}
    candidates = set(root.glob("*tools.py")) | set((root / "core").glob("*tools.py")) | set(root.glob("*_agent/*tools.py"))
    for path in sorted(candidates):
        relative = path.relative_to(root).as_posix()
        if relative in known or any(p in {".venv", "node_modules", ".git"} for p in path.parts):
            continue
        try:
            for fn in _tool_functions(_parse(path)):
                if not fn.name.startswith("calendar_"):
                    continue
                # Calendar tools are classified only as declared until their
                # explicit presence in the supervisor list can be established.
                agents = []
                for source, graph, list_name, owner, _ in SOURCES:
                    if (root / source).is_file() and (root / graph).is_file() and _uses_list(_parse(root / graph), list_name) and fn.name in _binding(_parse(root / source), list_name, root):
                        agents.append(owner)
                connected = bool(agents)
                entries.append(dict(id=f"{relative}:{fn.name}", name=fn.name,
                    description=" ".join((ast.get_docstring(fn) or "Operazione calendario.").split()),
                    group="Calendario", kind="tool", status="connected" if connected else "unconnected",
                    agents=agents, source=relative,
                    parameters=[a.arg for a in fn.args.args], detail="Disponibilità strutturale; non è un test di esecuzione."))
        except (OSError, SyntaxError) as error:
            errors.append(f"{relative}: {type(error).__name__}")

    # Registered routes are backend operations, not agent tools.
    for route in routes:
        path = getattr(route, "path", "")
        if path in {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", "/tools/inventory"}:
            continue
        group = ("File server" if "/server/files" in path else "Libreria IA" if "/library/files" in path else
                 "Architettura e tracce" if "/architecture/" in path or path.startswith("/api/v1/runs") else "Calendario" if "calendar" in path else "Memoria" if path.startswith("/memory") else
                 "Conversazioni" if path.startswith("/conversations") else "Sistema")
        for method in sorted(getattr(route, "methods", ()) or ()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            entries.append(dict(id=f"api:{method}:{path}", name=f"{method} {path}",
                description=getattr(route, "summary", None) or (getattr(route, "name", "Operazione backend").replace("_", " ")),
                group=group, kind="api", status="unconnected", agents=[], source="API registrata",
                parameters=[], detail="Endpoint disponibile al frontend; non costituisce un tool direttamente assegnato agli agenti."))

    planned = [
        ("calendar_list_events", "Calendario", "Elenco eventi in un intervallo di date."),
        ("calendar_get_event", "Calendario", "Dettagli di un evento."),
        ("calendar_create_event", "Calendario", "Proposta di creazione di un evento."),
        ("calendar_update_event", "Calendario", "Proposta di modifica di un evento."),
        ("calendar_delete_event", "Calendario", "Proposta di eliminazione di un evento."),
        ("Automazioni e modifica dei flussi", "Automazioni", "Predisposizione dell’interfaccia; API di validazione e pubblicazione ancora da costruire."),
        ("Editor ed esecuzione del codice", "Programmazione", "Interfaccia predisposta; tool di modifica ed esecuzione non implementati."),
        ("Allegati della chat", "Documenti", "Controllo UI predisposto; caricamento e associazione ai messaggi da implementare."),
        ("Microfono dalla UI", "Audio", "Controllo UI predisposto; acquisizione e invio al backend da implementare."),
    ]
    names = {e["name"] for e in entries}
    for name, group, description in planned:
        if name not in names:
            entries.append(dict(id=f"planned:{name}", name=name, description=description,
                group=group, kind="planned", status="planned", agents=[], source="Predisposizione / lavoro in corso",
                parameters=[], detail="Non utilizzabile nella versione di codice osservata. Non è una funzione operativa."))
    return {"entries": entries, "errors": errors, "scope": "Inventario strutturale del codice e delle API registrate; nessuna operazione eseguita."}
