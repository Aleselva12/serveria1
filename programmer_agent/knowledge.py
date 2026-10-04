"""Bundled skills/templates and bounded Graphify graph queries."""
from __future__ import annotations
import json
from pathlib import Path
from programmer_agent import workspace as ws

BASE = Path(__file__).resolve().parent
SKILLS = {
    "create-cora-tool": "Creare tool con contratti, permessi ed esempi verificabili.",
    "create-cora-automation": "Comporre automazioni e produrre bozze grafiche compatibili.",
    "verify-component": "Verificare sintassi e comportamento, distinguendo gli esiti.",
    "understand-project": "Orientarsi nel codice con catalogo, ricerca e Graphify.",
}
TEMPLATES = {"tool": "tool.py.txt", "tool_test": "tool_test.py.txt", "automation": "automation.json"}


def read_skill(name: str) -> str:
    if name not in SKILLS:
        raise ValueError("Skill non disponibile.")
    return (BASE / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def template(name: str) -> str:
    if name not in TEMPLATES:
        raise ValueError("Modello non disponibile.")
    return (BASE / "templates" / TEMPLATES[name]).read_text(encoding="utf-8")


def import_graph(identifier: str, graph: dict, source_digest: str) -> dict:
    if source_digest != ws.manifest(identifier)["source_digest"]:
        raise ValueError("Il grafo non corrisponde allo snapshot selezionato.")
    nodes, edges = graph.get("nodes"), graph.get("edges", graph.get("links"))
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > 20000 or len(edges) > 60000:
        raise ValueError("Grafo Graphify non valido o troppo grande.")
    nodes = [dict(node) if isinstance(node, dict) else node for node in nodes]
    ids = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), (str, int)) or str(node["id"]) in ids:
            raise ValueError("Identità dei nodi non valida.")
        ids.add(str(node["id"]))
    for edge in edges:
        if not isinstance(edge, dict) or any(not isinstance(edge.get(key), (str, int)) for key in ("source", "target")):
            raise ValueError("Collegamento non valido.")
        # Graphify includes import targets without a corresponding extracted node.
        # Preserve the relationship while making the missing definition explicit.
        for key in ("source", "target"):
            endpoint = str(edge[key])
            if endpoint not in ids:
                nodes.append({"id": endpoint, "label": endpoint, "unresolved": True,
                              "type": "unresolved_reference", "provenance": "adapter_placeholder"})
                ids.add(endpoint)
    if len(nodes) > 20000:
        raise ValueError("Grafo Graphify troppo grande dopo la normalizzazione.")
    value = {"source_digest": source_digest, "nodes": nodes, "edges": edges, "provider": "Graphify"}
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > 8_000_000:
        raise ValueError("Grafo oltre 8 MB.")
    ws._atomic(ws.directory(identifier) / "graph.json", encoded)
    return graph_status(identifier)


def graph_status(identifier: str) -> dict:
    path = ws.directory(identifier) / "graph.json"
    ws._no_links(path)
    if not path.exists():
        return {"available": False, "provider": "Graphify", "reason": "Importa il graph.json dello snapshot per abilitarne la consultazione."}
    graph = json.loads(path.read_text(encoding="utf-8"))
    modified = bool(ws.diff(identifier)["total_changes"])
    return {"available": True, "provider": "Graphify", "nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
            "stale": modified, "source_digest": graph["source_digest"],
            "scope": "Mappa dello snapshot iniziale; i collegamenti inferiti non sono una traccia runtime."}


def query_graph(identifier: str, query: str, node_id: str = "") -> dict:
    status = graph_status(identifier)
    if not status["available"]:
        return status
    path = ws.directory(identifier) / "graph.json"
    graph = json.loads(path.read_text(encoding="utf-8"))
    q = query.strip().lower()
    if not q and not node_id:
        raise ValueError("Indica testo di ricerca o un ID nodo.")
    nodes = [n for n in graph["nodes"] if str(n["id"]) == node_id] if node_id else [
        n for n in graph["nodes"] if q in json.dumps(n, ensure_ascii=False).lower()]
    ids = {str(n["id"]) for n in nodes[:10]}
    edges = [e for e in graph["edges"] if str(e.get("source")) in ids or str(e.get("target")) in ids]
    return {"status": status, "nodes": nodes[:10], "edges": edges[:30], "total_matches": len(nodes),
            "total_edges": len(edges), "truncated": len(nodes) > 10 or len(edges) > 30}
